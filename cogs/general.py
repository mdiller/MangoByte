import discord
from discord.ext import commands
from __main__ import settings, helpdoc, botdata
from cogs.utils.helpers import *
from cogs.utils import checks
import asyncio
import string
import random
from .mangocog import *


class General(MangoCog):
	"""General Commands
	"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	@commands.command(pass_context=True)
	async def ping(self, ctx, count : int=1):
		"""Pings a number of times(within reason)

		Pings... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await self.bot.say("thats not enough pings. stahp trying to break me.😠")
			return
		if count > 20:
			await self.bot.say("thats too many pings. stahp trying to break me.😠")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "Ping "
		await self.bot.say(ping_string)

	@commands.command(pass_context=True)
	async def echo(self, ctx, *, message : str):
		"""Echo...

		I would hurl words into this darkness and wait for an echo, and if an echo sounded, no matter how faintly, I would send other words to tell, to march, to fight, to create a sense of the hunger for life that gnaws in us all"""
		await self.bot.say(message)

	@commands.command(pass_context=True)
	async def changelog(self, ctx, count : int=5):
		"""Gets a rough changelog for mangobyte

		Count is how many versions to go back and give a log of. This is limited to 20 because of discord message size restrictions, and also to limit the amount of text that gets spammed in a channel.

		Note that this is a very rough changelog built from git commit messages and so will sometimes not relate directly to your perspective.

		For more commit versions or better detailed information, check out the source on GitHub: https://github.com/mdiller/MangoByte/commits/master
		"""
		if (count <= 0) or (count > int(get_version())):
			await self.bot.add_reaction(ctx.message, "😒")
			return
		elif count > 20:
			await self.bot.say("Count is limited to 20 versions.\nFor more versions or better detailed information, check out the source on GitHub: https://github.com/mdiller/MangoByte/commits/master")
			return
		else:
			await self.bot.say(get_changelog(count))
			return

	@commands.command(pass_context=True)
	async def info(self, ctx):
		"""Prints info about mangobyte"""
		github = "https://github.com/mdiller/MangoByte"
		python_version = "[Python {}.{}.{}]({})".format(*os.sys.version_info[:3], "https://www.python.org/")
		discordpy = "https://github.com/Rapptz/discord.py"

		embed = discord.Embed(description=helpdoc)

		embed.set_author(name=ctx.message.channel.server.me.nick, icon_url=self.bot.user.avatar_url, url=github)

		embed.add_field(name="Development Info", value=(
			"Developed as an open source project, hosted on [GitHub]({}). "
			"Implemented using {} and a python discord api wrapper [discord.py]({})".format(github, python_version, discordpy)))

		embed.add_field(name="Features", value=(
			"• Answers questions (?ask)\n"
			"• Plays audio clips (?play, ?dota)\n"
			"• Greets users joining a voice channel\n"
			"• Reacts to things people say 😉\n"
			"• For a full list of commands, try ?help"))

		owner = (await self.bot.application_info()).owner

		embed.set_footer(text="This MangoByte managed by {}".format(owner.name), icon_url=owner.avatar_url)

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def lasagna(self, ctx):
		"""A baked Italian dish

		Contains wide strips of pasta cooked and layered with meat or vegetables, cheese, and tomato sauce."""
		await self.bot.send_file(ctx.message.channel, settings.resourcedir + "images/lasagna.jpg")

	@checks.is_owner()
	@commands.command(pass_context=True, hidden=True)
	async def join(self, ctx, channel_id : str):
		new_channel = self.bot.get_channel(channel_id)
		if(new_channel == None):
			print("attempted to join invalid channel: " + channel_id)
			return

		audio = self.bot.get_cog("Audio")
		await audio.voice.move_to(new_channel)
		print("joined channel: " + channel_id)
		audio.voice_channel = self.bot.get_channel(channel_id)

	def __check(self, ctx):
		"""Checks to make sure the user has permissions"""
		if botdata.userinfo(ctx.message.author.id).banned:
			return False

		return True

	# @checks.is_owner()
	@commands.command(pass_context=True)
	async def botban(self, ctx, user: discord.User):
		"""Bans the user from using commands"""
		if not await checks.is_owner_check(ctx):
			await self.bot.say("You aint the boss of me 😠")
			return
		if user.id == (await ctx.bot.application_info()).owner.id:
			return # Dont mess with the owner's banned state
		botdata.userinfo(user.id).banned = True
		await self.bot.say("{} has henceforth been banned from using commands 😤".format(user.mention))


	# @checks.is_owner()
	@commands.command(pass_context=True)
	async def botunban(self, ctx, user: discord.User):
		"""Unbans the user, allowing them to use commands"""
		if not await checks.is_owner_check(ctx):
			await self.bot.say("You aint the boss of me 😠")
			return
		if user.id == (await ctx.bot.application_info()).owner.id:
			return # Dont mess with the owner's banned state
		botdata.userinfo(user.id).banned = False
		await self.bot.say("{} is free of their restraints and may once again use commands".format(user.mention))



def setup(bot):
	bot.add_cog(General(bot))