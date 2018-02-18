import discord
from cogs.utils.settings import Settings
from cogs.utils.botdata import BotData
from cogs.utils.helpers import *
from cogs.utils.helpformatter import MangoHelpFormatter
import cogs.utils.loggingdb as loggingdb
import traceback
import asyncio
import string
from discord.ext import commands
import logging
import datetime

logging.basicConfig(level=logging.INFO)

botdata = BotData()
settings = Settings()
loggingdb_session = loggingdb.create_session(settings.resource("loggingdb.db"))

# This have to be done after loading settings
from cogs.utils.httpgetter import HttpGetter
httpgetter = HttpGetter()
from cogs.utils.clip import *

description = """The juiciest unsigned 8 bit integer you is eva gonna see.
				For more information about me, try `{cmdpfx}info`"""
permissions = 314432

bot = commands.Bot(command_prefix='?', formatter=MangoHelpFormatter(), description=description)
bot.remove_command("help")
thinker = Thinker(bot)
invite_link = f"https://discordapp.com/oauth2/authorize?permissions={permissions}&scope=bot&client_id=213476188037971968"

deprecated_commands = {
	"ttschannel": "config ttschannel",
	"unttschannel": "config ttschannel none",
	"opendotasql": "https://www.opendota.com/explorer"
}

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Connecting to voice channels if specified in botdata.json ...')

	await bot.change_presence(game=discord.Game(name="DOTA 3 [?help]", url="http://github.com/mdiller/MangoByte"))
	cog = bot.get_cog("Audio")

	for guildinfo in botdata.guildinfo_list():
		if guildinfo.voicechannel is not None:
			try:
				print(f"connecting voice to: {guildinfo.voicechannel}")
				await cog.connect_voice(guildinfo.voicechannel)
			except UserError as e:
				if e.message == "channel not found":
					guildinfo.voicechannel = None
				else:
					raise
			except asyncio.TimeoutError:
				guildinfo.voicechannel = None
	

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

	try:
		if isinstance(error, commands.CommandNotFound):
			cmd = ctx.message.content[1:].split(" ")[0]
			if cmd in deprecated_commands:
				await ctx.send(f"You shouldn't use `?{cmd}` anymore. It's *deprecated*. Try `?{deprecated_commands[cmd]}` instead.")
				return
			elif cmd == "" or cmd.startswith("?") or cmd.startswith("!"):
				return # These were probably not meant to be commands

			if cmd.lower() in bot.commands:
				new_message = ctx.message
				new_message.content = "?" + cmd.lower() + ctx.message.content[len(cmd) + 1:]
				await bot.process_commands(new_message)
			elif await invalid_command_reporting(ctx):
				await ctx.send(f"🤔 Ya I dunno what a '{cmd}' is, but it ain't a command. Try `?help` fer a list of things that ARE commands.") 
		elif isinstance(error, commands.CheckFailure):
			print("(suppressed)")
			return # The user does not have permissions
		elif isinstance(error, commands.MissingRequiredArgument):
			await ctx.send(embed=await bot.formatter.format_as_embed(ctx, ctx.command))
		elif isinstance(error, commands.BadArgument):
			signature = await get_cmd_signature(ctx)
			await ctx.send((
				"Thats the wrong type of argument for that command.\n\n"
				f"Ya gotta do it like this:\n`{signature}`\n\n"
				f"Try `?help {ctx.command}` for a more detailed description of the command"))
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.errors.Forbidden):
			await print_missing_perms(ctx, error)
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.errors.HTTPException):
			await ctx.send("Looks like there was a problem with discord just then. Try again in a bit.")
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, UserError):
			await error.original.send_self(ctx)
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

	now_time = datetime.datetime.now() - datetime.timedelta(hours=3)

	error_list.append({
		"author": message.author.id,
		"message_id": message.id,
		"message": message.clean_content,
		"message_full": message.content,
		"date": now_time.strftime("%b %d  %-I:%M %p"),
		"command_error": type(error).__name__,
		"error": str(error),
		"traceback": trace
	})
	if settings.error_logging:
		write_json(error_file, error_list)
	trace_string = "\n".join(trace)
	print(f"\nError on: {message.clean_content}\n{trace_string}\n")
	return trace_string


if __name__ == '__main__':
	bot.load_extension("cogs.general")
	bot.load_extension("cogs.audio")
	bot.load_extension("cogs.dotabase")
	bot.load_extension("cogs.dotastats")
	bot.load_extension("cogs.pokemon")
	bot.load_extension("cogs.admin")
	bot.run(settings.token)


