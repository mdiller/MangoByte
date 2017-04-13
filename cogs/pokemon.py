import discord
from discord.ext import commands
from __main__ import settings, botdata
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
import aiohttp
import asyncio
import os
import re

async def pokeapi_query(querystring, fullurl=False):
	if not fullurl:
		url = "http://pokeapi.co/api/v2" + querystring
	else:
		url = querystring
	async with aiohttp.get(url) as r:
		if r.status == 200:
			return json.loads(await r.text(), object_pairs_hook=OrderedDict)
		elif r.status == 404:
			raise UserError("Pokemon not found")
		else:
			print("pokeapi errored on GET: '{}'".format(url))
			raise UserError("pokeapi said we did things wrong 😢. status code: {}".format(r.status))

def poke_color(color):
	return {
		"black": discord.Color(0x000000),
		"blue": discord.Color.blue(),
		"brown": discord.Color(0xD2691E),
		"gray": discord.Color(0xA9A9A9),
		"green": discord.Color.green(),
		"pink": discord.Color(0xFF69B4),
		"purple": discord.Color.purple(),
		"red": discord.Color.red(),
		"white": discord.Color(0xFFFFFF),
		"yellow": discord.Color(0xFFFF00)
	}[color]

class Pokemon(MangoCog):
	"""Pokemon related commands
	
	A few commands using the [pokeapi](https://pokeapi.co/) which provides information about pokemon"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	def poke_type(self, type_name):
		if type_name == "shadow" or type_name == "unknown":
			return type_name
		else:
			return self.get_emoji(f"poke_{type_name}")

	def clean_pokename(self, pokemon):
		pokemon = pokemon.lower()
		replacements = { " ": "-", "♂": "-m", "♀": "-f" }
		for key in replacements:
			pokemon = pokemon.replace(key, replacements[key])
		pokemon = re.sub(r'[^a-z0-9\-]', '', pokemon)
		return pokemon

	@commands.command(pass_context=True, aliases=["pokemon"])
	async def pokedex(self, ctx, *, pokemon):
		"""Looks up information about the indicated pokemon

		pokemon should be specified using either their name or id number

		Example:
		`{cmdpfx}pokedex charizard`"""

		# Sanitize input first
		pokemon = self.clean_pokename(pokemon)

		await self.bot.send_typing(ctx.message.channel)
		data = await pokeapi_query(f"/pokemon/{pokemon}/")
		species_data = await pokeapi_query(data["species"]["url"], True)
		types = []
		for t in sorted(data["types"], key=lambda t: t["slot"]):
			types.append(self.poke_type(t["type"]["name"]))

		def localize(list_data):
			for item in list_data:
				if item["language"]["name"] == "en":
					return item
			raise UserError("Error gathering pokemon data")

		flavor_text = localize(species_data["flavor_text_entries"])["flavor_text"]
		flavor_text = flavor_text.replace("\n", " ")

		embed = discord.Embed(description=flavor_text, color=poke_color(species_data["color"]["name"]))

		embed.set_author(name=localize(species_data["names"])["name"])

		embed.set_thumbnail(url=data["sprites"]["front_default"])

		embed.add_field(name=f"Type{'s' if len(types) > 1 else ''}", value=f"{''.join(types)}")
		if species_data.get("habitat"):
			embed.add_field(name="Habitat", value=f"{species_data['habitat']['name']}")
		embed.add_field(name="Weight", value=f"{data['weight'] / 10} kg")
		embed.add_field(name="Height", value=f"{data['height'] / 10} m")

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def shiny(self, ctx, *, pokemon):
		"""Gets the shiny version of this pokemon

		pokemon should be specified using either their name or id number

		Example:
		`{cmdpfx}shiny charizard`"""

		# Sanitize input first
		pokemon = self.clean_pokename(pokemon)
		await self.bot.send_typing(ctx.message.channel)
		data = await pokeapi_query(f"/pokemon/{pokemon}/")
		species_data = await pokeapi_query(data["species"]["url"], True)

		if not data["sprites"].get("front_shiny"):
			await self.bot.say("This pokemon doesn't have a shiny version")

		embed = discord.Embed(color=poke_color(species_data["color"]["name"]))
		embed.set_image(url=data["sprites"].get("front_shiny"))
		await self.bot.say(embed=embed)
	

def setup(bot):
	bot.add_cog(Pokemon(bot))