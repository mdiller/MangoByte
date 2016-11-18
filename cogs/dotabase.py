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
		self.hero_aliases = {}
		self.build_hero_aliases()

	def build_hero_aliases(self):
		for hero in session.query(Hero):
			self.hero_aliases[re.sub(r'[^a-z^A-Z]', r'', hero.name).lower()] = hero.id
			self.hero_aliases[re.sub(r'[^a-z^A-Z]', r'', hero.localized_name).lower()] = hero.id
			if " " in hero.localized_name:
				self.hero_aliases["".join(e[0] for e in hero.localized_name.lower().split())] = hero.id

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

		The format for input is the name of the sound.
		Some gooduns:
		?dota treant_move_20
		?dota troll_lose_03
		?dota timb_rare_01
		?dota slark_rare_02
		?dota drag_inthebag_01
		?dota bristle_inthebag_01
		?dota undying_gummy_vit_01
		?dota undying_gummy_vit_03
		?dota spir_move_26
		?dota beas_ability_animalsound_05
		?dota gyro_move_13

		If there is no response matching the input string, searches for any response that has the input string as part of its text 

		To specify a specific hero to search for responses for, use ';' before the hero's name like this:
		?dota ;rubick

		To search for a response, try using the web tool at:
		http://dotabase.me/responses/
		ProTip: If you click the discord button next to the response, it will copy to your clipboard in the format needed to play using the bot."""

		if keyphrase is None:
			words = []
		else:
			words = keyphrase.split(" ")

		hero = None
		for word in words:
			if word.startswith(";"):
				if not hero is None:
					await self.bot.say("Thats too many heroes")
					return
				# Get hero id
				hero = self.hero_aliases.get(word[1:])
				# Remove word and surrounding whitespace from keyphrase
				keyphrase = keyphrase.replace(word, "").strip()

				if hero is None:
					await self.bot.say("'" + word[1:] + "' isnt a hero")
					return

		query = await self.smart_dota_query(keyphrase, hero)

		# If we didnt find any responses no hero was specified, check for hidden heroes
		if query is None and hero is None:
			for word in words:
				hero = self.hero_aliases.get(word)
				if not hero is None:
					# Remove word and surrounding whitespace from keyphrase
					keyphrase = keyphrase.replace(word, "").strip()
					break

			if not hero is None:
				query = await self.smart_dota_query(keyphrase, hero)

		if query is None:
			await self.bot.say("No responses found! 😱");
		else:
			await self.play_response_query(query)


	async def smart_dota_query(self, keyphrase, hero=None):
		basequery = session.query(Response)
		if not hero is None:
			basequery = basequery.filter(Response.hero_id == hero)

		if keyphrase == None or keyphrase == "":
			return basequery

		query = basequery.filter(Response.name == keyphrase)
		if query.count() > 0:
			return query

		simple_input = " " + re.sub(r'[^a-z^0-9^A-Z^\s]', r'', keyphrase).lower() + " "

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