import discord
from cogs.utils.botdata import BotData
from cogs.utils.settings import Settings
from cogs.utils.helpers import *
from cogs.utils.helpformatter import MangoHelpFormatter
import asyncio
import string
from discord.ext import commands
import logging

logging.basicConfig(level=logging.INFO)

botdata = BotData()
settings = Settings()

from cogs.utils.clip import *# This has to be done after loading settings

description = """The juiciest unsigned 8 bit integer you is eva gonna see.
				For more information about me, try `{cmdpfx}info`"""

bot = commands.Bot(command_prefix='?', formatter=MangoHelpFormatter(), description=description)
bot.remove_command("help")
thinker = Thinker(bot)

deprecated_commands = {}

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Connecting to voice channels if specified in botdata.json ...')
	await bot.change_presence(game=discord.Game(name="DOTA 3 [?help]", url="http://github.com/mdiller/MangoByte"))
	await bot.get_cog("DotaStats").init_dicts()
	cog = bot.get_cog("Audio")

	for serverinfo in botdata.serverinfo_list():
		if serverinfo.voicechannel is not None:
			await cog.connect_voice(serverinfo.voicechannel)
	
	for server in bot.servers:
		if server.me.server_permissions.change_nickname:
			if server.me.nick is None or server.me.nick.startswith(bot.user.name):
				await bot.change_nickname(server.me, bot.user.name + " v" + get_version())

async def get_cmd_signature(ctx):
	bot.formatter.context = ctx
	bot.formatter.command = ctx.command
	return bot.formatter.get_command_signature()

# Whether or not we report invalid commands
async def invalid_command_reporting(ctx):
	if ctx.message.server is None:
		return True
	else:
		return botdata.serverinfo(ctx.message.server.id).invalidcommands

@bot.event
async def on_command_error(error, ctx):
	if ctx.message in thinker.messages:
		await thinker.stop_thinking(ctx.message)

	if isinstance(error, commands.CommandNotFound):
		cmd = ctx.message.content[1:].split(" ")[0]
		if cmd in deprecated_commands:
			await bot.send_message(ctx.message.channel, f"You shouldn't use `?{cmd}` anymore. It's *deprecated*. Try `?{deprecated_commands[cmd]}` instead.")
			return
		elif cmd == "" or cmd.startswith("?") or cmd.startswith("!"):
			return # These were probably not meant to be commands
		elif await invalid_command_reporting(ctx):
			await bot.send_message(ctx.message.channel, f"🤔 Ya I dunno what a '{cmd}' is, but it ain't a command. Try `?help` fer a list of things that ARE commands.") 
	elif isinstance(error, commands.CheckFailure):
		print("(suppressed)")
		return # The user does not have permissions
	elif isinstance(error, commands.MissingRequiredArgument):
		await bot.send_message(ctx.message.channel, embed=bot.formatter.format_as_embed(ctx, ctx.command))
	elif isinstance(error, commands.BadArgument):
		signature = await get_cmd_signature(ctx)
		await bot.send_message(ctx.message.channel, (
			"Thats the wrong type of argument for that command.\n\n"
			f"Ya gotta do it like this:\n`{signature}`\n\n"
			f"Try `?help {ctx.command}` for a more detailed description of the command"))
	elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, UserError):
		await bot.send_message(ctx.message.channel, error.original.message)
	else:
		await bot.send_message(ctx.message.channel, "Uh-oh, sumthin dun gone wrong 😱")
		print("errored while executing command {0}: {1}".format(ctx.command, error))
		raise error.original


if __name__ == '__main__':
	bot.load_extension("cogs.general")
	bot.load_extension("cogs.audio")
	bot.load_extension("cogs.dotastats")
	bot.load_extension("cogs.dotabase")
	bot.load_extension("cogs.ai")
	bot.load_extension("cogs.pokemon")
	bot.run(settings.token)

