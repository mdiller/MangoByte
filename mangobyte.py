import discord
from cogs.utils.botdata import BotData
from cogs.utils.settings import Settings
from cogs.utils.helpers import *
from cogs.utils.helpformatter import MangoHelpFormatter
from cogs.utils.loggingdb import create_session
import traceback
import asyncio
import string
from discord.ext import commands
import logging

logging.basicConfig(level=logging.INFO)

botdata = BotData()
settings = Settings()
loggingdb_session = create_session(settings.resource("loggingdb.db"))

# This have to be done after loading settings
from cogs.utils.clip import *
from cogs.utils.httpgetter import HttpGetter
httpgetter = HttpGetter()

description = """The juiciest unsigned 8 bit integer you is eva gonna see.
				For more information about me, try `{cmdpfx}info`"""

bot = commands.Bot(command_prefix='?', formatter=MangoHelpFormatter(), description=description)
bot.remove_command("help")
thinker = Thinker(bot)
invite_link = "https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot&client_id=213476188037971968"

deprecated_commands = {}

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Connecting to voice channels if specified in botdata.json ...')

	await bot.change_presence(game=discord.Game(name="DOTA 3 [?help]", url="http://github.com/mdiller/MangoByte"))
	cog = bot.get_cog("Audio")

	for guildinfo in botdata.guildinfo_list():
		if guildinfo.voicechannel is not None:
			try:
				await cog.connect_voice(guildinfo.voicechannel)
			except UserError as e:
				if e.message != "channel not found":
					raise
	
	for guild in bot.guilds:
		if guild.me.guild_permissions.change_nickname:
			if guild.me.nick is None or guild.me.nick.startswith(bot.user.name):
				await guild.me.edit(nick=bot.user.name + " v" + get_version())

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
		await ctx.send(f"Looks like I'm missing permissions 😢. Have an admin giff me back my permissions, or re-invite me to the server using this invite link: {invite_link}")
	elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, UserError):
		await ctx.send(error.original.message)
	else:
		await ctx.send("Uh-oh, sumthin dun gone wrong 😱")
		report_error(ctx.message, error)

error_file = "errors.json"

def report_error(message, error):
	if os.path.isfile(error_file):
		error_list = read_json(error_file)
	else:
		error_list = []

	try:
		raise error.original
	except:
		trace = traceback.format_exc().replace("\"", "'").split("\n")
		if len(trace) >= 6:
			del trace[1:5]
		trace = [x for x in trace if x] # removes empty lines

	error_list.append({
		"author": message.author.id,
		"message_id": message.id,
		"message": message.clean_content,
		"message_full": message.content,
		"command_error": type(error).__name__,
		"error": str(error),
		"traceback": trace
	})
	if settings.error_logging:
		write_json(error_file, error_list)
	trace_string = "\n".join(trace)
	print(f"\nError on: {message.clean_content}\n{trace_string}\n")


if __name__ == '__main__':
	bot.load_extension("cogs.general")
	bot.load_extension("cogs.audio")
	bot.load_extension("cogs.dotabase")
	bot.load_extension("cogs.dotastats")
	bot.load_extension("cogs.pokemon")
	bot.load_extension("cogs.admin")
	bot.run(settings.token)

