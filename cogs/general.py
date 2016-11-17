import discord
from discord.ext import commands
from __main__ import settings
from cogs.utils.helpers import *
from cogs.utils import checks
import asyncio
import string
import random


class General:
	"""General Commands
	"""
	def __init__(self, bot):
		self.bot = bot

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

	async def on_message(self, message):
		if (message.author == self.bot.user) or message.content.startswith("?"):
			return

		random.seed(message.content)

		if any(word in message.content for word in [ "sleep", "tired", "bye", "gnight", "goodnight" ]):
			await self.bot.add_reaction(message, "💤")
		elif any(word in message.content for word in [ "pizza", "food" ]):
			await self.bot.add_reaction(message, "🍕")
		elif ("!" in message.content) and (random.random() < 0.2):
			await self.bot.add_reaction(message, random.choice([ "😱", "‼" ]))
		elif ("?" in message.content) and (random.random() < 0.2):
			await self.bot.add_reaction(message, random.choice([ "🤔", "⁉" ]))
		elif random.random() < 0.05:
			await self.bot.add_reaction(message, "😉")



def setup(bot):
	bot.add_cog(General(bot))
