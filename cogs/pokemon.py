import discord
from discord.ext import commands
from __main__ import settings, botdata, httpgetter
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
import os
import re

async def pokeapi_query(url, fullurl=False):
	if not fullurl:
		url = f"http://pokeapi.co/api/v2{url}"
	return await httpgetter.get(url, cache=True, errors={
		404: "Pokemon not found",
		"default": "pokeapi said we did things wrong 😢. status code: {}"
	})

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


def localize(list_data, end_key):
	for item in list_data:
		if item["language"]["name"] == "en":
			return item[end_key]
	return None

class Pokemon(MangoCog):
	"""Pokemon related commands
	
	A few commands using the [pokeapi](https://pokeapi.co/) which provides information about pokemon

	Note that the above API does not include information about pokemon Sun and Moon, so I can't look up those pokemon for you"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	def poke_type(self, type_name):
		if type_name == "shadow" or type_name == "unknown":
			return type_name
		else:
			return self.get_emoji(f"poke_{type_name}")

	async def get_pokemon_data(self, pokemon):
		# Sanitize input first
		pokemon = pokemon.lower()
		replacements = { " ": "-", "♂": "-m", "♀": "-f" }
		for key in replacements:
			pokemon = pokemon.replace(key, replacements[key])
		pokemon = re.sub(r'[^a-z0-9\-]', '', pokemon)

		words = pokemon.split("-")
		if "mega" in words:
			words.remove("mega")
			words.insert(1, "mega")
			pokemon = "-".join(words)

		try:
			form_data = await pokeapi_query(f"/pokemon-form/{pokemon}/")
			data = await pokeapi_query(form_data["pokemon"]["url"], True)
		except Http404Error as e:
			form_data = None
			data = await pokeapi_query(f"/pokemon/{pokemon}/")
		species_data = await pokeapi_query(data["species"]["url"], True)

		data["localized_name"] = localize(species_data["names"], "name")
		if data["id"] >= 1000:
			data["id"] = species_data["id"]
		data["wiki_url"] = f"http://www.serebii.net/pokedex-sm/{data['id']:03d}.shtml"


		if form_data:
			data["sprites"] = form_data["sprites"]
			name = localize(form_data["names"], "name")
			if name:
				data["localized_name"] = name
			if form_data.get("is_mega"):
				data["wiki_url"] += "#mega"

		return data, species_data


	@commands.command(aliases=["pokemon"])
	async def pokedex(self, ctx, *, pokemon):
		"""Looks up information about the indicated pokemon

		Pokemon should be specified using either their name or id number

		Clicking on the pokemon's name will bring you to their wiki page

		Example:
		`{cmdpfx}pokedex charizard`"""
		with ctx.channel.typing():
			data, species_data = await self.get_pokemon_data(pokemon)

		types = []
		for t in sorted(data["types"], key=lambda t: t["slot"]):
			types.append(self.poke_type(t["type"]["name"]))

		flavor_text = localize(species_data["flavor_text_entries"], "flavor_text")
		flavor_text = flavor_text.replace("\n", " ")

		embed = discord.Embed(description=flavor_text, color=poke_color(species_data["color"]["name"]))
		embed.set_author(name=data["localized_name"] + f" #{data['id']}", url=data["wiki_url"])
		embed.set_thumbnail(url=data["sprites"]["front_default"])

		embed.add_field(name=f"Type{'s' if len(types) > 1 else ''}", value=f"{''.join(types)}")
		if species_data.get("habitat"):
			embed.add_field(name="Habitat", value=f"{species_data['habitat']['name']}")
		embed.add_field(name="Weight", value=f"{data['weight'] / 10} kg")
		embed.add_field(name="Height", value=f"{data['height'] / 10} m")

		await ctx.send(embed=embed)

	@commands.command()
	async def shiny(self, ctx, *, pokemon):
		"""Gets the shiny version of this pokemon

		pokemon should be specified using either their name or id number

		Example:
		`{cmdpfx}shiny charizard`"""

		# Sanitize input first
		with ctx.channel.typing():
			data, species_data = await self.get_pokemon_data(pokemon)

		if not data["sprites"].get("front_shiny"):
			await ctx.send("This pokemon doesn't have a shiny version")

		embed = discord.Embed(color=poke_color(species_data["color"]["name"]))
		embed.set_image(url=data["sprites"].get("front_shiny"))
		await ctx.send(embed=embed)
	

def setup(bot):
	bot.add_cog(Pokemon(bot))