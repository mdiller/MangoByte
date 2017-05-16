import discord
from discord.ext import commands
from __main__ import settings, botdata
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
import asyncio
import string
import random
import re
from cogs.audio import AudioPlayerNotFoundError


class AI(MangoCog):
	"""*Extremely* artificial intelligence
	
	A small selection of commands which showcase my immense wisdom"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.reactions = read_json(settings.resource("json/reactions.json"))
		self.questions = read_json(settings.resource("json/questions.json"))

	async def play_say_clip(self, responsename, ctx):
		clip = await self.get_clip("dota:" + responsename)
		await ctx.channel.send(clip.text)
		try:
			await self.play_clip(clip, ctx)
		except AudioPlayerNotFoundError:
			pass

	@commands.command()
	async def ask(self, ctx, *, question : str=""):
		"""Answers any question you might have"""
		random.seed(question)
		for check in self.questions:
			if re.search(check["regex"], question):
				await self.play_say_clip(random.choice(check["responses"]), ctx)
				return
		print("didnt match anything for ask")

	async def on_message(self, message):
		if message.content.startswith("?"):
			await self.log_message(message)

		if message.guild is not None and not botdata.guildinfo(message.guild.id).reactions:
			return

		if (message.author == self.bot.user) or message.content.startswith("?"):
			return

		random.seed(message.content)

		for check in self.reactions:
			expression = check["regex"]
			if check.get("word"):
				expression = "\\b({})\\b".format(expression)
				match = re.search(expression, message.clean_content, re.IGNORECASE)
			else:
				match = re.search(expression, message.clean_content)
			if match and (random.random() < check.get("chance", 1.0)):
				await message.add_reaction(random.choice(check["reaction"]))
				break


def setup(bot):
	bot.add_cog(AI(bot))