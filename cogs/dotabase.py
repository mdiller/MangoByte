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

	async def play_response(self, response):
		response_file = "http://dotabase.me/dota-vpk" + response.mp3
		audio = self.bot.get_cog("Audio")
		await audio.try_talking(response_file, volume=0.4)

	@commands.command(pass_context=True)
	async def dota(self, ctx, *, dota_response : str=None):
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

		To search for a response, try using the web tool at:
		http://dotabase.me/responses/
		ProTip: If you click the discord button next to the response, it will copy to your clipboard in the format needed to play using the bot."""
		if(dota_response == None):
			response = session.query(Response).order_by(func.random()).first()
			await self.play_response(response)
			return

		response1 = session.query(Response).filter(Response.name == dota_response).first()
		simple_input = "% " + re.sub(r'[^a-z^0-9^A-Z^\s]', r'', dota_response).lower() + " %"
		response2 = session.query(Response).filter(Response.text_simple.like(simple_input)).order_by(func.char_length(Response.text)).first()

		if(response1 != None):
			await self.play_response(response1)
		elif(response2 != None):
			await self.play_response(response2)
		else:
			await self.bot.say("Not a valid dota response, and no responses found with matching text 😱");

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
		dota_response = session.query(Response).filter(Response.text.like("no!")).order_by(func.random()).first()

		await self.play_response(dota_response)

	@commands.command(pass_context=True)
	async def yes(self, ctx):
		"""Ooooo ya."""
		dota_response = session.query(Response).filter(Response.text_simple == " yes ").order_by(func.random()).first()

		await self.play_response(dota_response)

	@commands.command(pass_context=True, aliases=["laugh", "haha", "lerl"])
	async def lol(self, ctx):
		"""WOW I WONDER WAT THIS DOES

		Laughs using dota. Thats what it does."""
		dota_response = session.query(Response).filter(Response.criteria.like("Emote%")).order_by(func.random()).first()

		await self.play_response(dota_response)

	@commands.command(pass_context=True, aliases=["ty"])
	async def thanks(self, ctx):
		"""Gives thanks

		Thanks are given by a random dota hero in their own special way"""
		dota_response = session.query(Response).filter(Response.criteria.like("Thanks%")).order_by(func.random()).first()

		await self.play_response(dota_response)

	@commands.command(pass_context=True)
	async def inthebag(self, ctx):
		"""Proclaims that 'IT' (whatever it is) is in the bag"""
		dota_response = session.query(Response).filter(and_(Response.criteria.like("InTheBag%"),Response.text != "It's in the bag!")).order_by(func.random()).first()

		await self.play_response(dota_response)

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