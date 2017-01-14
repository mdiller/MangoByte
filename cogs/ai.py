import discord
from discord.ext import commands
from __main__ import settings
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
import asyncio
import string
import random
import re


class AI(MangoCog):
	"""AI Commands
	"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.reactions = read_json(settings.resourcedir + "ai/reactions.json")
		self.questions = read_json(settings.resourcedir + "ai/questions.json")

	async def play_say_clip(self, responsename):
		clip = await self.get_clip("dota:" + responsename)
		await self.bot.say(clip.text)
		await self.play_clip(clip)

	@commands.command(pass_context=True)
	async def ask(self, ctx, *, question : str=""):
		"""Answers any question you might have"""
		random.seed(question)
		for check in self.questions:
			if re.search(check["regex"], question):
				await self.play_say_clip(random.choice(check["responses"]))
				return
		print("didnt match anything for ask")


	async def on_message(self, message):
		if message.content.startswith("?"):
			print("--> {0}: {1}".format(message.author, message.content))

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
				await self.bot.add_reaction(message, random.choice(check["reaction"]))
				break


def setup(bot):
	bot.add_cog(AI(bot))