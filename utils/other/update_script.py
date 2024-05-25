import inspect
import json
import inspect
import typing

import cogs.dotastats
import utils.command.commandargs
import utils.tools.botdata as botdata
from dotabase import Hero, Facet
from disnake.ext import commands
from utils.tools.globals import settings, logger, httpgetter
from utils.tools.helpers import *


# Note: This code used to be in mangobyte.py so look there for more history

# a script to update static files for mangobyte
async def update(bot: commands.Bot):
	print("Update script started")
	await bot.wait_until_ready()
	print("bot is ready")
	
	print("- Updating generated files...")
	replacements_dict = {
		"COMMANDS": None,
		"MATCH_FILTER_COMMANDS": None,
		"MATCH_ARGUMENT_COMMANDS": None,
		"CONFIG_SETTINGS": None,
		"USERCONFIG_SETTINGS": None,
		"INVITE_LINK": f"[Invite Link]({settings.invite_link})"
	}

	target_files = [
		"README.md",
		"docs/docs.md",
		"docs/slash_command_common_issues.md"
	]

	# Get fill value for COMMANDS

	commands_file = "resource/json/commands.json"
	data = {
		"cogs": [],
		"commands": []
	}
	for cmd in bot.commands:
		if cmd.cog and cmd.cog.name == "Owner":
			continue
		data["commands"].append({
			"name": cmd.name,
			"short_help": cmd.short_doc,
			"help": cmd.help,
			"aliases": cmd.aliases,
			"cog": cmd.cog.name if cmd.cog else "General",
			"prefix": "?"
		})
	for cmd in slash_command_expand(bot.slash_commands):
		if isinstance(cmd, commands.SubCommand):
			cogname = cmd.help_cog_name
			description = cmd.body.description
		else:
			cogname = cmd.help_cog_name
			description = cmd.description
		data["commands"].append({
			"name": cmd.qualified_name,
			"signature": None,
			"short_help": description,
			"help": description,
			"aliases": [],
			"cog": cogname,
			"prefix": "/"
		})
	for cog in bot.cogs:
		if cog == "Owner":
			continue
		data["cogs"].append({
			"name": cog,
			"short_help": bot.cogs[cog].description.split('\n')[0],
			"help":  bot.cogs[cog].description
		})
	data["commands"] = list(sorted(data["commands"], key=lambda c: c["name"]))

	with open(commands_file, "w+") as f:
		f.write(json.dumps(data, indent="\t"))

	max_command_len = max(map(lambda c: len(c["name"]), data["commands"]))
	max_short_help_len = max(map(lambda c: len(c["short_help"]), data["commands"]))

	docs = ""
	docs += f"Mangobyte currently has {len(data['commands'])} commands, separated into {len(data['cogs'])} categories\n"
	for cog in data["cogs"]:
		docs += f"\n#### {cog['name']}\n"
		docs += f"{cog['short_help']}\n"
		docs += "\n```\n"
		for cmd in data["commands"]:
			if cmd["cog"] == cog["name"]:
				docs += f"{cmd['prefix']}{cmd['name']: <{max_command_len + 1}} | {cmd['short_help']: <{max_short_help_len + 1}}\n"
		docs += "```\n"

	replacements_dict["COMMANDS"] = docs

	# Get fill values for args stuff
	
	replacements_dict["MATCH_ARGUMENT_COMMANDS"] = get_commands_with_arg(bot, cogs.dotastats.DotaMatch)
	replacements_dict["MATCH_FILTER_COMMANDS"] = get_commands_with_arg(bot, utils.command.commandargs.MatchFilter)

	# Get fill values for /userconfig and /config settings
	def setting_variables_list_names(variables):
		lines = []
		for variable in variables:
			if not variable.get("disabled"):
				lines.append(f"- {variable.get('key')}")
		return "\n".join(lines) + "\n"
	replacements_dict["CONFIG_SETTINGS"] = setting_variables_list_names(botdata.guildinfo_variables)
	replacements_dict["USERCONFIG_SETTINGS"] = setting_variables_list_names(botdata.userinfo_variables)

	# Update all the files with the new values

	for filename in target_files:
		with open(filename, "r") as f:
			text = f.read()
		for key,value in replacements_dict.items():
			replacement_start = f"<!-- {key}_START -->\n?"
			replacement_end = f"\n?<!-- {key}_END -->"
			text = re.sub(f"({replacement_start}).*?({replacement_end})", f"\\g<1>{value}\\2", text, flags=re.S)
		with open(filename, "w+") as f:
			f.write(text)
	
	print("- Updating emoji...")
	await update_emoji(bot)

	print("done!")

# gets a list of commands that take the given arg type
def get_commands_with_arg(bot, argtype):
	matching_commands = []
	all_commands = slash_command_expand(bot.slash_commands)
	all_commands.extend(bot.commands)
	for cmd in all_commands:
		for paramtype in typing.get_type_hints(cmd._callback).values():
			if paramtype is argtype or paramtype is typing.Optional[argtype]: # 
				name = cmd.qualified_name
				prefix = "?" if isinstance(cmd, commands.Command) else "/"
				matching_commands.append(f"{prefix}{name}")
				break
	matching_commands.sort()
	return "\n".join(map(lambda c: f"`{c}`", matching_commands))

async def update_emoji(bot: commands.Bot):
	emoji_json_file = settings.resource("json/emoji.json")
	emoji_json = read_json(emoji_json_file)
	if settings.emoji_dev_servers is None:
		print("Can't update emoji without 'emoji_dev_servers' set in settings file")
		return
	# guild = bot.get_guild(settings.emoji_dev_servers)

	emoji_guilds: typing.List[disnake.Guild]
	emoji_guilds = []
	for server_id in settings.emoji_dev_servers:
		emoji_guilds.append(bot.get_guild(server_id))

	existing_emojis = []
	for guild in emoji_guilds:
		existing_emojis.extend(guild.emojis)

	EMOJI_PER_SERVER_LIMIT = 48
	
	open_slots = (EMOJI_PER_SERVER_LIMIT * len(emoji_guilds)) - len(existing_emojis)
	print(f"{open_slots} open emoji slots")
	
	# add any extra emoji that we dont have
	for guild in emoji_guilds:
		for emoji in guild.emojis:
			if emoji.name not in emoji_json:
				imgpath = settings.resource(f"images/emojis/{emoji.name}.png")
				with open(imgpath, 'wb+') as f:
					f.write((await httpgetter.get(str(emoji.url), return_type="bytes")).read())
				print(f"recording '{emoji.name}' emoji")
				emoji_json[emoji.name] = emoji.id

	emojis_to_add = [] # tuples of emoji_name, image url

	dotabase = bot.get_cog("Dotabase")
	# check for any missing heroes
	for hero in dotabase.session.query(Hero):
		hero: Hero
		emoji_name =f"dota_hero_{hero.name}"
		if emoji_name not in emoji_json:
			emojis_to_add.append((emoji_name, dotabase.vpkurl + hero.icon))

	# check for any missing facet icons
	for facet in dotabase.session.query(Facet):
		facet: Facet
		emoji_name =f"dota_facet_icon_{facet.icon_name}"
		if len(emoji_name) > 32:
			emoji_name = emoji_name[:32]
		if emoji_name not in emoji_json:
			emojis_to_add.append((emoji_name, dotabase.vpkurl + facet.icon))

	guild_index = 0
	guild_slots_available = 0
	# add the new dota emojis
	for emoji_name, emoji_url in emojis_to_add:
		print(f"Adding new emoji {emoji_name}")
		image = await httpgetter.get(emoji_url, return_type="filename", cache=True)
		with open(image, "rb") as f:
			image = f.read()
		
		while guild_index < len(emoji_guilds) and guild_slots_available <= 0:
			guild_index += 1
			guild_slots_available = EMOJI_PER_SERVER_LIMIT - len(emoji_guilds[guild_index].emojis)
		if guild_index >= len(emoji_guilds):
			print("RAN OUT OF ROOM FOR NEW EMOJIS!!!!!!!!!!\n\n\nNEED NEW EMOJIS GUILD!!!!")
			break
	
		emoji = await emoji_guilds[guild_index].create_custom_emoji(name=emoji_name, image=image, reason=f"New Dota emoji")
		emoji_json[emoji_name] = emoji.id
		guild_slots_available -= 1

	write_json(emoji_json_file, emoji_json)
	
	await bot.close()