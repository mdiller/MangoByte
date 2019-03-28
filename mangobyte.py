
# The following have to be imported and initialized in the correct order
from cogs.utils.settings import Settings
settings = Settings()

from cogs.utils.botdata import BotData
botdata = BotData()

import cogs.utils.loggingdb as loggingdb
loggingdb_session = loggingdb.create_session(settings.resource("loggingdb.db"))

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
from cogs.utils.helpformatter import MangoHelpFormatter
from cogs.utils.clip import *

logging.basicConfig(level=logging.INFO)


description = """The juiciest unsigned 8 bit integer you is eva gonna see.
				For more information about me, try `{cmdpfx}info`"""
permissions = 314432

bot = commands.Bot(command_prefix=botdata.command_prefix_botmessage, formatter=MangoHelpFormatter(), description=description)
bot.remove_command("help")
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
	"register": "userconfig steam"
}

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Connecting to voice channels if specified in botdata.json ...')

	game = discord.Activity(
		name="DOTA 3 [?help]", 
		type=discord.ActivityType.playing,
		start=datetime.datetime.utcnow())
	await bot.change_presence(status=discord.Status.online, activity=game)
	audio_cog = bot.get_cog("Audio")
	artifact_cog = bot.get_cog("Artifact")
	await artifact_cog.load_card_sets()

	# stuff to help track/log the connection of voice channels
	start_time = datetime.datetime.now()
	connected_count = 0
	not_found_count = 0
	timeout_count = 0

	for guildinfo in botdata.guildinfo_list():
		if guildinfo.voicechannel is not None:
			try:
				print(f"connecting voice to: {guildinfo.voicechannel}")
				await audio_cog.connect_voice(guildinfo.voicechannel)
				print(f"connected: {guildinfo.voicechannel}")
				connected_count += 1
			except UserError as e:
				if e.message == "channel not found":
					guildinfo.voicechannel = None
					print("channel not found!")
					not_found_count += 1
				else:
					raise
			except asyncio.TimeoutError:
				guildinfo.voicechannel = None
				print("timeout error when connecting to channel")
				timeout_count += 1

	print("\nupdating guilds")
	loggingdb.update_guilds(bot.guilds, loggingdb_session)
	
	print("\ninitialization finished\n")

	message = "__**Initialization complete:**__"
	if connected_count > 0:
		message += f"\n{connected_count} voice channels connected"
	if not_found_count > 0:
		message += f"\n{not_found_count} voice channels not found"
	if timeout_count > 0:
		message += f"\n{timeout_count} voice channels timed out"

	appinfo = await bot.application_info()
	if not settings.debug:
		await appinfo.owner.send(message)

async def get_cmd_signature(ctx):
	bot.formatter.context = ctx
	bot.formatter.command = ctx.command
	return bot.formatter.get_command_signature()

# Whether or not we report invalid commands
async def invalid_command_reporting(ctx):
	if ctx.message.guild is None:
		return True
	else:
		return botdata.guildinfo(ctx.message.guild.id).invalidcommands

@bot.event
async def on_command_error(ctx, error):
	if ctx.message in thinker.messages:
		await thinker.stop_thinking(ctx.message)

	cmdpfx = botdata.command_prefix(ctx)

	loggingdb.command_finished(ctx, "errored", type(error).__name__, loggingdb_session)
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
			await ctx.send(embed=await bot.formatter.format_as_embed(ctx, ctx.command))
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
			loggingdb.command_finished(ctx, "user_errored", error.original.message, loggingdb_session)
			await error.original.send_self(ctx, botdata)
		else:
			await ctx.send("Uh-oh, sumthin dun gone wrong 😱")
			trace_string = report_error(ctx.message, error, skip_lines=4)
			if settings.debug:
				await ctx.send(f"```{trace_string}```")
	except discord.errors.Forbidden:
		await ctx.author.send("Looks like I don't have permission to talk in that channel, sorry")

error_file = "errors.json"

async def print_missing_perms(ctx, error):
	if not (ctx.guild):
		await ctx.send("Uh-oh, sumthin dun gone wrong 😱")
		trace_string = report_error(ctx.message, error, skip_lines=0)
	my_perms = ctx.channel.permissions_for(ctx.guild.me)
	perms_strings = read_json(settings.resource("json/permissions.json"))
	perms = []
	for i in range(0, 32):
		if ((permissions >> i) & 1) and not my_perms._bit(i):
			words = perms_strings["0x{:08x}".format(1 << i)].split("_")
			for i in range(0, len(words)):
				words[i] = f"**{words[i][0] + words[i][1:].lower()}**"
			perms.append(" ".join(words))
	if perms:
		await ctx.send("Looks like I'm missin' these permissions 😢:\n" + "\n".join(perms))
	else:
		await ctx.send(f"Looks like I'm missing permissions 😢. Have an admin giff me back my permissions, or re-invite me to the server using this invite link: {invite_link}")


def report_error(message, error, skip_lines=2):
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

	loggingdb.insert_error(message, error, trace_string, loggingdb_session)

	print(f"\nError on: {message.clean_content}\n{trace_string}\n")
	return trace_string



if __name__ == '__main__':
	bot.load_extension("cogs.general")
	bot.load_extension("cogs.audio")
	bot.load_extension("cogs.dotabase")
	bot.load_extension("cogs.dotastats")
	bot.load_extension("cogs.pokemon")
	bot.load_extension("cogs.artifact")
	bot.load_extension("cogs.admin")
	bot.load_extension("cogs.owner")
	bot.run(settings.token)


