import discord
from discord.ext import commands
from .utils.settings import *
import asyncio
import string


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
			await self.bot.say("thats not enough pings. stahp trying to break me.")
			return
		if count > 21:
			await self.bot.say("thats too many pings. stahp trying to break me.")
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

	@commands.command(pass_context=True, hidden=True)
	async def join(self, ctx, channel_id : str):
		appinfo = await self.bot.application_info()
		if(appinfo.owner.id == ctx.message.author.id):
			new_channel = self.bot.get_channel(channel_id)
			if(new_channel == None):
				print("attempted to join invalid channel: " + channel_id)
				return

			await self.voice.move_to(new_channel)
			print("joined channel: " + channel_id)
			self.voice_channel = self.bot.get_channel(channel_id)
		else:
			print("non-owner tried to use owner command")


def setup(bot):
	bot.add_cog(General(bot))
