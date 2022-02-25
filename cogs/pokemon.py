import disnake
from disnake.ext import commands
from __main__ import settings, botdata, httpgetter
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
from cogs.audio import AudioPlayerNotFoundError
import os
import re
import logging
logger = logging.getLogger("mangologger")

async def pokeapi_query(url, fullurl=False):
	if not fullurl:
		url = f"http://pokeapi.co/api/v2{url}"
	return await httpgetter.get(url, cache=True, errors={
		404: "Pokemon not found",
		"default": "pokeapi said we did things wrong 😢. status code: {}"
	})

def poke_color(color):
	return {
		"black": disnake.Color(0x000000),
		"blue": disnake.Color.blue(),
		"brown": disnake.Color(0xD2691E),
		"gray": disnake.Color(0xA9A9A9),
		"green": disnake.Color.green(),
		"pink": disnake.Color(0xFF69B4),
		"purple": disnake.Color.purple(),
		"red": disnake.Color.red(),
		"white": disnake.Color(0xFFFFFF),
		"yellow": disnake.Color(0xFFFF00)
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

	# returns True on success, False on failure
	async def play_pokecry(self, ctx, poke_id, namestring, old=False):
		is_mega = "mega" in str(namestring).lower()

		name = str(poke_id)
		if old:
			name = f"old/{name}"
		if is_mega:
			name = f"{name}-mega"

		try:
			clip = await self.get_clip(f"url:http://dillerm.io/data/pokemon_cries/{name}.ogg", ctx)
			clip.volume = 0.1
			await self.play_clip(clip, ctx)
		except Http404Error:
			return False
		except AudioPlayerNotFoundError:
			return True

		return True


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

		embed = disnake.Embed(description=flavor_text, color=poke_color(species_data["color"]["name"]))
		embed.title = data["localized_name"] + f" #{data['id']}"
		embed.url = data["wiki_url"]

		embed.set_thumbnail(url=data["sprites"]["front_default"])

		embed.add_field(name=f"Type{'s' if len(types) > 1 else ''}", value=f"{''.join(types)}")
		if species_data.get("habitat"):
			embed.add_field(name="Habitat", value=f"{species_data['habitat']['name']}")
		embed.add_field(name="Weight", value=f"{data['weight'] / 10} kg")
		embed.add_field(name="Height", value=f"{data['height'] / 10} m")

		# fails silently if there's no cry for this pokemon
		await self.play_pokecry(ctx, data["id"], pokemon)

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

		embed = disnake.Embed(color=poke_color(species_data["color"]["name"]))
		embed.set_image(url=data["sprites"].get("front_shiny"))

		# fails silently if there's no cry for this pokemon
		await self.play_pokecry(ctx, data["id"], pokemon)

		await ctx.send(embed=embed)
	
	@commands.command(aliases=["cry"])
	async def pokecry(self, ctx, *, pokemon):
		"""Plays the pokemon's sound effect

		Audio files for these pokemon cries were gotten from [Veekun](https://veekun.com/dex/downloads). Veekun does not have the cries for Generation VII yet, so I won't be able to play those.

		Most pokemon have a new cry and an old cry. To get the old cry instead of the new one, add 'old' to the end of your command (see example below.)

		**Example:**
		`{cmdpfx}pokecry pikachu`
		`{cmdpfx}pokecry bulbasaur old`"""
		words = pokemon.split(" ")
		old = "old" in words
		if old:
			words.remove("old") 
		pokemon = " ".join(words)

		data, species_data = await self.get_pokemon_data(pokemon)

		if data["id"] > 721:
			raise UserError("Sorry, I don't have the cries for pokemon in Generation VII yet")

		success = await self.play_pokecry(ctx, data["id"], pokemon, old=old)

		if not success:
			raise UserError(f"Couldn't find the cry for {data['localized_name']}")


def setup(bot):
	bot.add_cog(Pokemon(bot))