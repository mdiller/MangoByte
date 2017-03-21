import discord
from discord.ext import commands
from sqlalchemy.sql.expression import func
from sqlalchemy import and_, or_
from __main__ import settings
from cogs.utils.helpers import *
from cogs.utils.clip import *
import random
import os
import asyncio
import string
import re
from .mangocog import *
from dotabase import *

session = dotabase_session()


# A variable that can specify a filter on a query
class QueryVariable():
	def __init__(self, name, aliases, query_filter, prefix=";"):
		self.name = name
		self.aliases = aliases
		self.query_filter = query_filter
		self.prefix = prefix
		self.value = None

	def __repr__(self):
		if self.value is None:
			return self.name + " not set"
		else:
			return self.name + " = " + self.value

	def apply_filter(self, query):
		return self.query_filter(query, self.value)

# extracts variables from the given words, removing them when extracted
# extracts all words with the prefix, throwing a UserError if finding too many of a given variable or an invalid one
def extract_var_prefix(words, variables):
	for i in range(0, len(words)):
		word = words[i]
		prefix = None
		for var in variables:
			if word.startswith(var.prefix):
				prefix = var.prefix
				if word[len(prefix):] in var.aliases:
					if var.value is not None:
						raise UserError("Ya can't specify more than one " + var.name + ", ya doofus")
					var.value = var.aliases[word[len(prefix):]]
					words.remove(word)
					extract_var_prefix(words, variables)
					return
		if prefix is not None: # The word has a prefix valid for one or more variables
			raise UserError("No idea what a '" + word[len(prefix):] + "' is")

# extracts the first word that matches any variable
# returns true if a variable was found
def extract_var(words, variables):
	for i in range(0, len(words)):
		word = words[i]
		for var in variables:
			if (var.value is None) and (word in var.aliases):
				var.value = var.aliases[word]
				words.remove(word)
				return True
	return False


class Dotabase(MangoCog):
	"""Dota hero response commands

	Interfaces with [dotabase](http://github.com/mdiller/dotabase). Check out [dotabase.me](http://dotabase.me) if you want to see a website that interfaces with dotabase."""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.criteria_aliases = read_json(settings.resourcedir + "json/criteria_aliases.json")
		self.hero_aliases = {}
		self.build_aliases()
		self.vpkurl = "http://dotabase.me/dota-vpk"

	def build_aliases(self):
		for hero in session.query(Hero):
			aliases = hero.aliases.replace(" ", "").split("|")
			for alias in aliases:
				self.hero_aliases[alias] = hero.id

		for crit in session.query(Criterion).filter(Criterion.matchkey == "Concept"):
			self.criteria_aliases[crit.name.lower()] = crit.name

	async def get_hero_infos(self):
		result = {}
		for hero in session.query(Hero):
			result[hero.id] = {
				"name": hero.localized_name,
				"full_name": hero.full_name,
				"icon": self.vpkurl + hero.icon,
				"attr": {
					"DOTA_ATTRIBUTE_STRENGTH": "str",
					"DOTA_ATTRIBUTE_AGILITY": "agi",
					"DOTA_ATTRIBUTE_INTELLECT": "int"
				}[hero.attr_primary]
			}
			#this to replace the ones below
		return result

	async def play_response(self, response):
		await self.play_clip("dota:" + response.name)

	def get_response(self, responsename):
		return session.query(Response).filter(Response.name == responsename).first()

	# Plays a random response from a query
	async def play_response_query(self, query):
		await self.play_response(query.order_by(func.random()).first())

	@commands.command(pass_context=True)
	async def dota(self, ctx, *, keyphrase : str=None):
		"""Plays a dota response

		First tries to match the keyphrase with the name of a response

		If there is no response matching the input string, searches for any response that has the input string as part of its text 

		To specify a specific hero to search for responses for, use ';' before the hero's name like this:
		`{cmdpfx}dota ;rubick`

		To specify a specific criteria to search for responses for, use ';' before the criteria name like this:
		`{cmdpfx}dota ;rubick ;defeat`
		There are some aliases for heroes, so the following will work:
		`{cmdpfx}dota sf`
		`{cmdpfx}dota furion`
		`{cmdpfx}dota shredder`

		If failing all of the above, the command will also try to find unlabeled heroes and critera. try:
		`{cmdpfx}dota juggernaut bottling`
		A few critera you can use are: kill, bottling, cooldown, acknowledge, immortality, nomana, and select

		To search for a response without asking mangobyte, try using the [Response Searcher](http://dotabase.me/responses/) at Dotabase.me
		ProTip: If you click the discord button next to the response in the above web app, it will copy to your clipboard in the format needed to play using the bot."""
		variables = [
			QueryVariable("hero", self.hero_aliases, lambda query, value: query.filter(Response.hero_id == value)),
			QueryVariable("criteria", self.criteria_aliases, lambda query, value: query.filter(or_(Response.criteria.like(value + "%"), Response.criteria.like("%|" + value + "%")))),
		]

		if keyphrase is None:
			words = []
		else:
			keyphrase = keyphrase.lower()
			words = keyphrase.split(" ")

		extract_var_prefix(words, variables)

		query = await self.smart_dota_query(words, variables)

		while query is None and extract_var(words, variables):
			query = await self.smart_dota_query(words, variables)

		if query is None:
			await self.bot.say("No responses found! 😱");
		else:
			await self.play_response_query(query)


	async def smart_dota_query(self, words, variables):
		basequery = session.query(Response)
		for var in variables:
			if var.value is not None:
				basequery = var.apply_filter(basequery)

		keyphrase = " ".join(words)

		if keyphrase == None or keyphrase == "" or keyphrase == " ":
			if basequery.count() > 0:
				return basequery
			else:
				return None

		# Because some of wisp's responses are not named correctly
		if '_' in keyphrase:
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
		"""Oooooh ya."""
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


def setup(bot):
	bot.add_cog(Dotabase(bot))