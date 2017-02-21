import discord
from cogs.utils.botdata import BotData
from cogs.utils.settings import Settings
from cogs.utils.helpers import *
from cogs.utils.helpformatter import MangoHelpFormatter
import asyncio
import string
from discord.ext import commands

botdata = BotData()
settings = Settings()

from cogs.utils.clip import *# This has to be done after loading settings

description = """**MangoByte** - The juiciest unsigned 8 bit integer you eva gonna see
				For more info about Mangobyte, try `{cmdpfx}info`
				
				To get more information about a specific command, try `{cmdpfx}help <command>`"""

bot = commands.Bot(command_prefix='?', formatter=MangoHelpFormatter(), description=description)
bot.remove_command("help")


deprecated_commands = {}

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Automatically connecting to default channel via ID...')
	cog = bot.get_cog("Audio")

	for serverinfo in botdata.serverinfo_list():
		if serverinfo.voicechannel is not None:
			await cog.connect_voice(serverinfo.voicechannel)

	# await bot.change_nickname(cog.voice.channel.server.me, bot.user.name + " v" + get_version())
	# clip = await cog.get_clip("local:bothello")
	# clip.volume = 0.1
	# await cog.play_clip(clip)

async def get_cmd_signature(ctx):
	# formatter = commands.HelpFormatter()
	# formatter.command = command
	bot.formatter.context = ctx
	bot.formatter.command = ctx.command
	return bot.formatter.get_command_signature()

@bot.event
async def on_command_error(error, ctx):
	if isinstance(error, commands.CommandNotFound):
		cmd = ctx.message.content[1:].split(" ")[0]
		if cmd in deprecated_commands:
			await bot.send_message(ctx.message.channel, "You shouldn't use `?{}` anymore. It's *deprecated*. Try `?{}` instead.".format(cmd, deprecated_commands[cmd]))
			return
		await bot.send_message(ctx.message.channel, "🤔 Ya I dunno what a '{}' is, but it ain't a command. Try `?help` fer a list of things that ARE commands.".format(cmd)) 
	elif isinstance(error, commands.CheckFailure):
		print("(suppressed)")
		return # The user does not have permissions
	elif isinstance(error, commands.MissingRequiredArgument):
		await bot.send_message(ctx.message.channel, "Well **thats** not right. 🙃 Yer missin some arguments. Ya gotta do it like this:\n\n`{}`\n\nTry doin `?help {}` ta figure out what yer doin wrong.".format(await get_cmd_signature(ctx), ctx.command))
	elif isinstance(error, commands.BadArgument):
		await bot.send_message(ctx.message.channel, "No... no no no. 😩 Thats the wrong type of argument for that command. Ya gotta do it like this:\n\n`{}`\n\nYa might need ta do `?help {}` and **actually read** what I say 😒.".format(await get_cmd_signature(ctx), ctx.command))
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
	bot.run(settings.token)
