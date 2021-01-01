
# The following have to be imported and initialized in the correct order
from cogs.utils.settings import Settings
settings = Settings()

from cogs.utils.botdata import BotData
botdata = BotData()

from cogs.utils.loggingdb import LoggingDb
loggingdb = LoggingDb(settings.resource("loggingdb.db"))

from cogs.utils.httpgetter import HttpGetter
httpgetter = HttpGetter()

from cogs.utils.helpers import *
import discord
import traceback
import asyncio
import string
from discord.ext import commands
import logging
import datetime
from cogs.utils.helpcommand import MangoHelpCommand
from cogs.utils.clip import *
from cogs.utils.commandargs import *
import json
import sys
import inspect

startupTimer = SimpleTimer()

if not os.path.exists("logs"):
    os.makedirs("logs")
# DISCORDPY LOGGING IS NOT NEEDED AT THE MOMENT, SO ILL DISABLE THIS LOGGING FOR NOW
# print("setting up logger!")
# timestamp = datetime.datetime.now().strftime("%Y-%m-%d__%I.%M%p")
# logger = logging.getLogger("discord")
# logger.setLevel(logging.INFO)
# handler = logging.FileHandler(filename=f"logs/discord_{timestamp}.log", encoding="utf-8", mode="w")
# handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s", "%Y-%m-%d %I:%M:%S%p"))
# logger.addHandler(handler)

description = """The juiciest unsigned 8 bit integer you is eva gonna see.
				For more information about me, try `{cmdpfx}info`"""
permissions = 314432

bot = commands.AutoShardedBot(command_prefix=botdata.command_prefix_botmessage, help_command=MangoHelpCommand(), description=description, shard_count=(2 if settings.debug else 10))

thinker = Thinker(bot)
invite_link = f"https://discordapp.com/oauth2/authorize?permissions={permissions}&scope=bot&client_id=213476188037971968"

deprecated_commands = {
	"ttschannel": "config ttschannel",
	"unttschannel": "config ttschannel none",
	"opendotasql": "https://www.opendota.com/explorer",
	"setintrotts": "userconfig introtts",
	"setwelcome": "userconfig introtts",
	"setoutrotts": "userconfig outrotts",
	"setintro": "userconfig intro",
	"setoutro": "userconfig outro",
	"setsteam": "userconfig steam",
	"register": "userconfig steam",
	"friendstats": "playerstats with @Player"
}

on_ready_has_run = False

@bot.event
async def on_shard_ready(shard_id):
	appinfo = await bot.application_info()
	await appinfo.owner.send(f"shard {shard_id} ({len(bot.shards)} total) called its on_shard_ready ({len(bot.guilds)} guilds)")

@bot.event
async def on_ready():
	appinfo = await bot.application_info()
	await appinfo.owner.send(f"{len(bot.guilds)} guilds in bot.guilds at the beginning of on_ready()")

	global on_ready_has_run
	is_first_time = True
	if on_ready_has_run:
		is_first_time = False
		print("on_ready called again, waiting 10 seconds before processing")
		await asyncio.sleep(10)
	on_ready_has_run = True

	onReadyTimer = SimpleTimer()

	if is_first_time:
		print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
		print('Connecting to voice channels if specified in botdata.json ...')

	game = discord.Activity(
		name="DOTA 3 [?help]", 
		type=discord.ActivityType.playing,
		start=datetime.datetime.utcnow())
	await bot.change_presence(status=discord.Status.online, activity=game)

	general_cog = bot.get_cog("General")
	audio_cog = bot.get_cog("Audio")
	dota_cog = bot.get_cog("Dotabase")
	artifact_cog = bot.get_cog("Artifact")
	await artifact_cog.load_card_sets()
	bot.help_command.cog = bot.get_cog("General")

	periodic_tasks = [
		general_cog.update_topgg,
		general_cog.check_dota_patch,
                dota_cog.check_dota_blog
	]
	# start topgg update service thing
	for task in periodic_tasks:
		if (not task.is_running()):
			task.start()

	channel_tasks = []
	for guildinfo in botdata.guildinfo_list():
		if guildinfo.voicechannel is not None:
			channel_tasks.append(initial_channel_connect_wrapper(audio_cog, guildinfo))

	channel_connector = AsyncBundler(channel_tasks)

	# actually do the awaiting of the channel connections
	await channel_connector.wait()

	if is_first_time:
		print("\nupdating guilds")
		await loggingdb.update_guilds(bot.guilds)
	
	finished_text = "initialization finished"
	if not is_first_time:
		finished_text = "re-" + finished_text
	print(f"\n{finished_text}\n")

	message = "__**Initialization complete:**__"
	if not is_first_time:
		message = "__**Re-Initialization complete (shard prolly got poked):**__"

	message += "\n" + channel_connector.status_as_string("voice channels connected")

	message += f"\n\non_ready took {onReadyTimer}"
	if is_first_time:
		message += f"\nFull startup took {startupTimer}"
	appinfo = await bot.application_info()

	if not settings.debug:
		await appinfo.owner.send(message)

	appinfo = await bot.application_info()
	await appinfo.owner.send(f"{len(bot.guilds)} guilds in bot.guilds at the end of on_ready()")


async def get_cmd_signature(ctx):
	bot.help_command.context = ctx
	return bot.help_command.get_command_signature(ctx.command)

# Whether or not we report invalid commands
async def invalid_command_reporting(ctx):
	if ctx.message.guild is None:
		return True
	else:
		return botdata.guildinfo(ctx.message.guild.id).invalidcommands

async def initial_channel_connect_wrapper(audio_cog, guildinfo):
	channel_id = guildinfo.voicechannel
	server_id = guildinfo.id
	print(f"connecting voice to: {channel_id}")
	await initial_channel_connect(audio_cog, guildinfo)
	print(f"connected: {channel_id}")


# returns 0 on successful connect, 1 on not found, and 2 on timeout, 3 on error
async def initial_channel_connect(audio_cog, guildinfo):
	global on_ready_has_run
	channel_id = guildinfo.voicechannel
	status = "connected"
	try:
		connect_task = audio_cog.connect_voice(guildinfo.voicechannel)
		await asyncio.wait_for(connect_task, timeout=200)
		return "connected"
	except UserError as e:
		if e.message == "channel not found":
			guildinfo.voicechannel = None
			raise
		else:
			print(f"weird usererror on connection to channel '{channel_id}': {e.message}")
			raise
	except asyncio.TimeoutError:
		if not on_ready_has_run: # don't remove this if it got timed out from a re-initialization
			guildinfo.voicechannel = None
		raise
	except Exception as e:
		print(f"exception thrown on connection to channel ({channel_id}): {str(e)}")
		guildinfo.voicechannel = None
		raise


@bot.event
async def on_command_error(ctx, error):
	if ctx.message.id in thinker.messages:
		await thinker.stop_thinking(ctx.message)

	cmdpfx = botdata.command_prefix(ctx)

	if not (isinstance(error, commands.CommandInvokeError) and isinstance(error.original, UserError)):
		await loggingdb.command_finished(ctx, "errored", type(error).__name__)

	try:
		if isinstance(error, commands.CommandNotFound):
			cmd = ctx.message.content[1:].split(" ")[0]
			if cmd in deprecated_commands:
				await ctx.send(f"You shouldn't use `{cmdpfx}{cmd}` anymore. It's *deprecated*. Try `{cmdpfx}{deprecated_commands[cmd]}` instead.")
				return
			elif cmd == "" or cmd.startswith("?") or cmd.startswith("!"):
				return # These were probably not meant to be commands

			if cmd.lower() in bot.commands:
				new_message = ctx.message
				new_message.content = cmdpfx + cmd.lower() + ctx.message.content[len(cmd) + 1:]
				await bot.process_commands(new_message)
			elif await invalid_command_reporting(ctx):
				await ctx.send(f"🤔 Ya I dunno what a '{cmd}' is, but it ain't a command. Try `{cmdpfx}help` fer a list of things that ARE commands.") 
		elif isinstance(error, commands.CheckFailure):
			emoji_dict = read_json(settings.resource("json/emoji.json"))
			if botdata.guildinfo(ctx).is_disabled(ctx.command):
				await ctx.message.add_reaction(bot.get_emoji(emoji_dict["command_disabled"]))
			else:
				await ctx.message.add_reaction(bot.get_emoji(emoji_dict["unauthorized"]))
			return # The user does not have permissions
		elif isinstance(error, commands.MissingRequiredArgument):
			help_command = bot.help_command.copy()
			help_command.context = ctx
			await help_command.command_callback(ctx, command=ctx.command.name)
		elif isinstance(error, CustomBadArgument):
			await error.user_error.send_self(ctx, botdata)
		elif isinstance(error, commands.BadArgument):
			signature = await get_cmd_signature(ctx)
			await ctx.send((
				"Thats the wrong type of argument for that command.\n\n"
				f"Ya gotta do it like this:\n`{signature}`\n\n"
				f"Try `{cmdpfx}help {ctx.command}` for a more detailed description of the command"))
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.errors.Forbidden):
			await print_missing_perms(ctx, error)
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.errors.HTTPException):
			await ctx.send("Looks like there was a problem with discord just then. Try again in a bit.")
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, UserError):
			await error.original.send_self(ctx, botdata)
			await loggingdb.command_finished(ctx, "user_errored", error.original.message)
		elif isinstance(error, commands.ConversionError) and isinstance(error.original, UserError):
			await error.original.send_self(ctx, botdata)
			await loggingdb.command_finished(ctx, "user_errored", error.original.message)					
		else:
			await ctx.send("Uh-oh, sumthin dun gone wrong 😱")
			trace_string = await report_error(ctx.message, error, skip_lines=4)
			if settings.debug:
				await ctx.send(f"```{trace_string}```")
	except discord.errors.Forbidden:
		try:
			await ctx.author.send("Looks like I don't have permission to talk in that channel, sorry")
		except discord.errors.Forbidden:
			pass

error_file = "errors.json"

async def print_missing_perms(ctx, error):
	if not (ctx.guild):
		await ctx.send("Uh-oh, sumthin dun gone wrong 😱")
		trace_string = await report_error(ctx.message, error, skip_lines=0)
	my_perms = ctx.channel.permissions_for(ctx.guild.me)
	perms_strings = read_json(settings.resource("json/permissions.json"))
	perms = []
	for i in range(0, 32):
		if ((permissions >> i) & 1) and not ((permissions >> i) & 1):
			words = perms_strings["0x{:08x}".format(1 << i)].split("_")
			for i in range(0, len(words)):
				words[i] = f"**{words[i][0] + words[i][1:].lower()}**"
			perms.append(" ".join(words))
	if perms:
		await ctx.send("Looks like I'm missin' these permissions 😢:\n" + "\n".join(perms))
	else:
		await ctx.send(f"Looks like I'm missing permissions 😢. Have an admin giff me back my permissions, or re-invite me to the server using this invite link: {invite_link}")


async def report_error(message, error, skip_lines=2):
	if os.path.isfile(error_file):
		error_list = read_json(error_file)
	else:
		error_list = []

	try:
		raise error.original
	except:
		trace = traceback.format_exc().replace("\"", "'").split("\n")
		if skip_lines > 0 and len(trace) >= (2 + skip_lines):
			del trace[1:(skip_lines + 1)]
		trace = [x for x in trace if x] # removes empty lines
	
	trace_string = "\n".join(trace)

	await loggingdb.insert_error(message, error, trace_string)

	print(f"\nError on: {message.clean_content}\n{trace_string}\n")
	return trace_string

def update_commandinfo():
	commands_file = "resource/json/commands.json"
	data = {
		"cogs": [],
		"commands": []
	}
	commands = sorted(bot.commands, key=lambda c: c.name) 
	for cmd in commands:
		if cmd.cog and cmd.cog.name == "Owner":
			continue
		data["commands"].append({
			"name": cmd.name,
			"signature": bot.help_command.get_command_signature(cmd),
			"short_help": cmd.short_doc,
			"help": bot.help_command.fill_template(cmd.help),
			"aliases": cmd.aliases,
			"cog": cmd.cog.name if cmd.cog else "General"
		})
	for cog in bot.cogs:
		if cog == "Owner":
			continue
		data["cogs"].append({
			"name": cog,
			"short_help": bot.help_command.cog_short_doc(bot.cogs[cog]),
			"help":  inspect.getdoc(bot.cogs[cog])
		})

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
				docs += f"?{cmd['name']: <{max_command_len + 1}} | {cmd['short_help']: <{max_short_help_len + 1}}\n"
		docs += "```\n"

	readme_file = "README.md"
	readme_replacement_start = "<!-- COMMANDS_START -->\n"
	readme_replacement_end = "\n<!-- COMMANDS_END -->"
	with open(readme_file, "r") as f:
		text = f.read()
	text = re.sub(f"({readme_replacement_start}).*({readme_replacement_end})", f"\\1{docs}\\2", text, flags=re.S)
	with open(readme_file, "w+") as f:
		f.write(text)

	print("done!")


from cogs.general import General
from cogs.audio import Audio
from cogs.dotabase import Dotabase
from cogs.dotastats import DotaStats
from cogs.pokemon import Pokemon
from cogs.artifact import Artifact
from cogs.admin import Admin
from cogs.owner import Owner

if __name__ == '__main__':
	bot.add_cog(General(bot))
	bot.add_cog(Audio(bot))
	bot.add_cog(Dotabase(bot))
	bot.add_cog(DotaStats(bot))
	bot.add_cog(Pokemon(bot))
	bot.add_cog(Artifact(bot))
	bot.add_cog(Admin(bot))
	bot.add_cog(Owner(bot))

	if len(sys.argv) > 1 and sys.argv[1] == "commands":
		update_commandinfo()
	else:
		print(f"Starting mango at {datetime.datetime.today().strftime('%d-%b-%Y %I:%M %p')}")
		bot.run(settings.token)


