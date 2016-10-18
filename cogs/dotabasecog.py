import discord
from discord.ext import commands
from .utils.settings import *
from audio import playaudio
import asyncio
import string


class DotabaseCog:
	"""Commands for interfacing with Dotabase. See dotabase.me for a website that interfaces with Dotabase.
	"""
	def __init__(self, bot):
		self.bot = bot

	@commands.command(pass_context=True)
	async def dota(self, ctx, dota_response : str):
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

		To search for a response, try using the web tool at:
		http://dotabase.me/responses/
		ProTip: If you click the discord button next to the response, it will copy to your clipboard in the format needed to play using the bot."""
		response_file = findfile(dota_response + ".mp3", settings.dotavpk + "sounds/vo/")
		if(response_file != None):
			await playaudio(self.bot, ctx, response_file, volume=0.4)
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
		response = random.choice(dota_hellos)
		print("hello: " + response)
		await playaudio(self.bot, ctx, findfile(response + ".mp3", settings.dotavpk + "sounds/vo/"), volume=0.4)
