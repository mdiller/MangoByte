import discord
from cogs.utils.botdata import BotData
from cogs.utils.settings import Settings
from cogs.utils.helpers import *
import asyncio
import string
from discord.ext import commands

helpdoc = """MangoByte - The juiciest unsigned 8 bit integer ever to be hosted on github: https://github.com/mdiller/MangoByte"""


botdata = BotData()
settings = Settings()
bot = commands.Bot(command_prefix='?', description=helpdoc)


@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Automatically connecting to default channel via ID...')
	cog = bot.get_cog("Audio")
	cog.voice = await bot.join_voice_channel(bot.get_channel(settings.defaultvoice))
	await bot.change_nickname(cog.voice.channel.server.me, bot.user.name + " v" + get_version())
	await cog.try_talking(settings.resourcedir + "clips/dota/bothello.mp3", volume=0.1)

@bot.event
async def on_command_error(error, ctx):
	if isinstance(error, commands.MissingRequiredArgument):
		await bot.send_message(ctx.message.channel,
				"need moar arguments on command ?{0} try doin ?help {0} to see how its done.".format(ctx.command))
	elif isinstance(error, commands.BadArgument):
		await bot.send_message(ctx.message.channel,
				"need better arguments on command ?{0} try doin ?help {0} to see how its done.".format(ctx.command))
	else:
		print("error executing command {0}: {1}".format(ctx.command, error))

if __name__ == '__main__':
	bot.load_extension("cogs.general")
	bot.load_extension("cogs.audio")
	bot.load_extension("cogs.dotastats")
	bot.load_extension("cogs.dotabase")
	bot.load_extension("cogs.ai")
	bot.run(settings.token)
