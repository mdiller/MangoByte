import inspect
import json
import inspect
import typing

import cogs.dotastats
import utils.command.commandargs
from disnake.ext import commands
from utils.tools.globals import settings, logger
from utils.tools.helpers import *


# Note: This code used to be in mangobyte.py so look there for more history

# a script to update static files for mangobyte
def update(bot: commands.Bot):
	replacements_dict = {
		"COMMANDS": None,
		"SLASH_PROGRESS_PERCENT": None,
		"MATCH_FILTER_COMMANDS": None,
		"MATCH_ARGUMENT_COMMANDS": None,
		"INVITE_LINK": f"[Invite Link]({settings.invite_link})"
	}

	target_files = [
		"README.md",
		"resource/docs.md",
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
			"signature": bot.help_command.get_command_signature(cmd),
			"short_help": cmd.short_doc,
			"help": bot.help_command.fill_template(cmd.help),
			"aliases": cmd.aliases,
			"cog": cmd.cog.name if cmd.cog else "General",
			"prefix": "?"
		})
	for cmd in bot.help_command.expand_subcommands(bot.slash_commands):
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
			"short_help": bot.help_command.cog_short_doc(bot.cogs[cog]),
			"help":  inspect.getdoc(bot.cogs[cog])
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

	# Get fill value for SLASH_PROGRESS_PERCENT

	total_count = len(data["commands"])
	slash_count = len(list(filter(lambda c: c["prefix"] == "/", data["commands"])))
	percent_value = str(round(100 * slash_count / total_count)) + "%"
	replacements_dict["SLASH_PROGRESS_PERCENT"] = percent_value

	# Get fill values for args stuff
	
	replacements_dict["MATCH_ARGUMENT_COMMANDS"] = get_commands_with_arg(bot, cogs.dotastats.DotaMatch)
	replacements_dict["MATCH_FILTER_COMMANDS"] = get_commands_with_arg(bot, utils.command.commandargs.MatchFilter)

	# Update all the files with the n	ew values

	for filename in target_files:
		with open(filename, "r") as f:
			text = f.read()
		for key,value in replacements_dict.items():
			replacement_start = f"<!-- {key}_START -->\n?"
			replacement_end = f"\n?<!-- {key}_END -->"
			text = re.sub(f"({replacement_start}).*?({replacement_end})", f"\\g<1>{value}\\2", text, flags=re.S)
		with open(filename, "w+") as f:
			f.write(text)

# gets a list of commands that take the given arg type
def get_commands_with_arg(bot, argtype):
	matching_commands = []
	all_commands = bot.help_command.expand_subcommands(bot.slash_commands)
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