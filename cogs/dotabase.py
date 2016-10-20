import discord
from discord.ext import commands
from sqlalchemy.sql.expression import func
from .utils.settings import *
import random
import os
import asyncio
import string
from dotabase import *

session = dotabase_session()

class Dotabase:
	"""Commands for interfacing with Dotabase. See http://dotabase.me for a website that interfaces with Dotabase.
	"""
	def __init__(self, bot):
		self.bot = bot

	async def play_response(self, response):
		response_file = settings.dotavpk + response.mp3
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
		response2 = session.query(Response).filter(Response.text_simple.like("% " + dota_response + " %")).order_by(func.char_length(Response.text)).first()

		if(response1 != None):
			await self.play_response(response1)
		elif(response2 != None):
			await self.play_response(response2)
		else:
			await self.bot.say("Not a valid dota response");

	@commands.command(pass_context=True)
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

	@commands.command(pass_context=True)
	async def no(self, ctx):
		"""Nopes."""
		dota_response = session.query(Response).filter(Response.text.like("no!")).order_by(func.random()).first()

		await self.play_response(dota_response)

def setup(bot):
	bot.add_cog(Dotabase(bot))