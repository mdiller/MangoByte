import discord
from discord.ext import commands
from sqlalchemy.sql.expression import func
from sqlalchemy import and_
from __main__ import settings
import random
import os
import asyncio
import string
import re
from dotabase import *

session = dotabase_session()


class Dotabase:
	"""Commands for interfacing with Dotabase. See http://dotabase.me for a website that interfaces with Dotabase.
	"""
	def __init__(self, bot):
		self.bot = bot
		self.criteria_aliases = {}
		self.hero_aliases = {}
		self.build_aliases()

	def build_aliases(self):
		for hero in session.query(Hero):
			self.hero_aliases[re.sub(r'[^a-z^A-Z]', r'', hero.name).lower()] = hero.id
			self.hero_aliases[re.sub(r'[^a-z^A-Z]', r'', hero.localized_name).lower()] = hero.id
			if " " in hero.localized_name:
				self.hero_aliases["".join(e[0] for e in hero.localized_name.lower().split())] = hero.id

		for crit in session.query(Criterion).filter(Criterion.matchkey == "Concept"):
			self.criteria_aliases[crit.name.lower()] = crit.name


	async def play_response(self, response):
		response_file = "http://dotabase.me/dota-vpk" + response.mp3
		audio = self.bot.get_cog("Audio")
		await audio.try_talking(response_file, volume=0.4)

	# Plays a random response from a query
	async def play_response_query(self, query):
		await self.play_response(query.order_by(func.random()).first())

	@commands.command(pass_context=True)
	async def dota(self, ctx, *, keyphrase : str=None):
		"""Plays a dota response

		First tries to match the keyphrase with the name of a response

		If there is no response matching the input string, searches for any response that has the input string as part of its text 

		To specify a specific hero to search for responses for, use ';' before the hero's name like this:
		?dota ;rubick

		To specify a specific criteria to search for responses for, use '.' before the criteria name like this:
		?dota ;rubick .defeat
		There are some aliases for heroes, so the following will work:
		?dota sf
		?dota furion
		?dota shredder
		But there are some aliases that will not work, like magina

		If failing all of the above, the command will also try to find unlabeled heroes and critera. try:
		?dota juggernaut bottling
		A few critera you can use are: kill, bottling, cooldown, acknowledge, immortality, nomana, and select
		Check the dropdown box at http://dotabase.me/responses/ for more criteria names

		To search for a response, try using the web tool at:
		http://dotabase.me/responses/
		ProTip: If you click the discord button next to the response, it will copy to your clipboard in the format needed to play using the bot."""

		if keyphrase is None:
			words = []
		else:
			keyphrase = keyphrase.lower()
			words = keyphrase.split(" ")

		hero = await self.keyphrase_variable(words, self.hero_aliases, "hero", ";")
		criteria = await self.keyphrase_variable(words, self.criteria_aliases, "criteria", ".")

		query = await self.smart_dota_query(" ".join(words), hero, criteria)

		if query is None and hero is None:
			hero = await self.keyphrase_variable(words, self.hero_aliases, "hero")
			if hero is not None:
				query = await self.smart_dota_query(" ".join(words), hero, criteria)

		if query is None and criteria is None:
			criteria = await self.keyphrase_variable(words, self.criteria_aliases, "criteria")
			if criteria is not None:
				query = await self.smart_dota_query(" ".join(words), hero, criteria)


		if query is None:
			await self.bot.say("No responses found! 😱");
		else:
			await self.play_response_query(query)

	# Extracts the variable from the words if it finds it and removes it from the words
	async def keyphrase_variable(self, words, aliases_dict, varname, prefix=""):
		for i in range(0, len(words)):
			word = words[i]
			if prefix == "" or word.startswith(prefix):
				# Get variable
				var = aliases_dict.get(word[len(prefix):])
				if var is not None:
					# Remove word from keyphrase
					words.remove(word)
					return var

				if prefix != "":
					await self.bot.say("'" + word[len(prefix):] + "' isnt a " + varname)
					return None
		return None

	async def smart_dota_query(self, keyphrase, hero, criteria):
		basequery = session.query(Response)
		if hero is not None:
			basequery = basequery.filter(Response.hero_id == hero)
		if criteria is not None:
			basequery = basequery.filter(Response.criteria.like(criteria + " %"))

		if keyphrase == None or keyphrase == "" or keyphrase == " ":
			return basequery

		query = basequery.filter(Response.name == keyphrase)
		if query.count() > 0:
			return query

		simple_input = " " + re.sub(r'[^a-z^0-9^A-Z^\s]', r'', keyphrase) + " "

		query = basequery.filter(Response.text_simple == simple_input)
		if query.count() > 0:
			return query

		query = basequery.filter(Response.text_simple.like("%" + simple_input + "%"))
		if query.count() > 0:
			return query

		return None

	@commands.command(pass_context=True, aliases=["hi"])
	async def hello(self, ctx):
		"""Says hello

		WHAT MORE DO YOU NEED TO KNOW!?!?!? IS 'Says hello' REALLY NOT CLEAR ENOUGH FOR YOU!?!!11?!!?11!!?!??"""
		dota_hellos = [
			"slark_attack_11",
			"kunk_thanks_02",
			"meepo_scepter_06",
			"puck_ability_orb_03",
			"tink_spawn_07",
			"treant_ally_08",
			"wraith_lasthit_02",
			"timb_deny_08",
			"tech_pain_39",
			"meepo_attack_08",
			"slark_lasthit_02",
			"gyro_move_26"
		]
		dota_response = random.choice(dota_hellos)
		response = session.query(Response).filter(Response.name == dota_response).first()
		print("hello: " + response.name)
		await self.play_response(response)

	@commands.command(pass_context=True, aliases=["nope"])
	async def no(self, ctx):
		"""Nopes."""
		await self.play_response_query(session.query(Response).filter(Response.text.like("no!")))

	@commands.command(pass_context=True)
	async def yes(self, ctx):
		"""Ooooo ya."""
		await self.play_response_query(session.query(Response).filter(Response.text_simple == " yes "))

	@commands.command(pass_context=True, aliases=["laugh", "haha", "lerl"])
	async def lol(self, ctx):
		"""WOW I WONDER WAT THIS DOES

		Laughs using dota. Thats what it does."""
		await self.play_response_query(session.query(Response).filter(Response.criteria.like("Emote%")))

	@commands.command(pass_context=True, aliases=["ty"])
	async def thanks(self, ctx):
		"""Gives thanks

		Thanks are given by a random dota hero in their own special way"""
		await self.play_response_query(session.query(Response).filter(Response.criteria.like("Thanks%")))

	@commands.command(pass_context=True)
	async def inthebag(self, ctx):
		"""Proclaims that 'IT' (whatever it is) is in the bag"""
		await self.play_response_query(session.query(Response).filter(and_(Response.criteria.like("InTheBag%"),Response.text != "It's in the bag!")))

	@commands.command(pass_context=True)
	async def ask(self, ctx, *, question : str=""):
		"""Answers any question you might have"""
		answers = [
			"orac_purifyingflames_09", #yes
			"orac_falsepromise_02", #outcome unclear
			"orac_kill_08", #ask again later
			"orac_falsepromise_14", #yes, as forseen
			"orac_fatesedict_17", #why not
			"orac_notyet_01", #not yet
			"orac_lose_01", #no
			"orac_attack_01" #could go either way
		]
		random.seed(question)
		dota_response = random.choice(answers)
		response = session.query(Response).filter(Response.name == dota_response).first()
		await self.bot.say(response.text)
		await self.play_response(response)

def setup(bot):
	bot.add_cog(Dotabase(bot))