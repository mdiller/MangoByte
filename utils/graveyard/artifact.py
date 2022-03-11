import disnake
from disnake.ext import commands
from __main__ import settings, botdata, httpgetter
from cogs.utils.deck_decoder import ParseDeck
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils.card import *
from cogs.utils import checks
from cogs.utils import drawdota
from .mangocog import *
import random
import os
import re
import json
import logging
logger = logging.getLogger("mangologger")

class Artifact(MangoCog):
	"""Artifact related commands
	
	A few commands providing information about Valve's new game [Artifact](https://playartifact.com)"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.card_sets_uri = "artifact_card_sets"
		self.card_sets = []
		self.cards = []

	async def load_card_sets(self):
		card_sets_filename = httpgetter.cache.get_filename(self.card_sets_uri)

		if card_sets_filename is None:
			await self.update_card_sets()
			return

		self.card_sets = []
		self.cards = []
		for set_data in read_json(card_sets_filename):
			card_set = CardSet(set_data)
			self.card_sets.append(card_set)
			for card_data in set_data["card_list"]:
				self.cards.append(Card(card_data, card_set))
		for card in self.cards:
			card.update_references(self.get_card)

		self.card_names = OrderedDict()
		for card in self.cards:
			if card.name:
				if card.name.lower() not in self.card_names or card.large_image:
					self.card_names[card.name.lower()] = card.id

	async def update_card_sets(self):
		card_sets_data = []
		for n in range(0, 100):
			try:
				set_data = await httpgetter.get(f"https://playartifact.com/cardset/{str(n).zfill(2)}")
			except HttpError as e:
				if e.code == 400:
					break # this set doesnt exist yet
				else:
					raise
			except json.decoder.JSONDecodeError as e:
				break # valve has removed the api D:
			data = (await httpgetter.get(f"{set_data['cdn_root']}{set_data['url']}"))["card_set"]
			card_sets_data.append(data)

		card_sets_filename = await httpgetter.cache.new(self.card_sets_uri, "json")
		write_json(card_sets_filename, card_sets_data)

		await self.load_card_sets()

	def get_card(self, card_id):
		for card in self.cards:
			if card.id == card_id:
				return card
		return None

	# there is a better way to do this but im lazy and tired right now
	def find_card(self, name):
		if name == "":
			return None
		if name is None:
			return self.get_card(random.choice(list(self.card_names.values())))
		name = name.lower()
		for card_name in self.card_names:
			if name == card_name:
				return self.get_card(self.card_names[card_name])
		for card_name in self.card_names:
			if name in card_name.split(" "):
				return self.get_card(self.card_names[card_name])
		for card_name in self.card_names:
			if name in card_name:
				return self.get_card(self.card_names[card_name])
		pattern = r"[^a-z]"
		name = re.sub(pattern, "", name)
		if name == "":
			return None
		for card_name in self.card_names:
			if name == re.sub(pattern, "", card_name):
				return self.get_card(self.card_names[card_name])
		for card_name in self.card_names:
			if name in re.sub(pattern, "", card_name):
				return self.get_card(self.card_names[card_name])
		return None

	@checks.is_owner()
	@commands.command(hidden=True)
	async def updateartifact(self, ctx):
		"""Updates all the artifact card data"""
		await self.update_card_sets()
		await ctx.message.add_reaction("✅")


	@commands.command(aliases=["artifact"])
	async def card(self, ctx, *, card_name : str=None):
		"""Displays info about the artifact card
		
		Example:
		`{cmdpfx}artifact Healing Salve`
		`{cmdpfx}artifact Prowler Vanguard`
		`{cmdpfx}artifact keefe`"""
		card = self.find_card(card_name)

		if card is None:
			raise UserError(f"Couldn't find any card with the name '{card_name}'")

		embed = disnake.Embed(color=disnake.Color(card.color.integer))
		if card.mini_image:
			embed.set_author(name=card.name, icon_url=card.mini_image)
		else:
			embed.set_author(name=card.name)
		
		if card.large_image:
			embed.set_image(url=card.large_image)
		elif card.text:
			embed.description = card.text

		if card.references:
			descriptions = []
			for ref in card.references:
				ref_type = format_pascal_case(ref.ref_type.replace("_", " "))
				if ref.count:
					ref_type += f" (x{ref.count})"
				if ref.card.name == card.name:
					continue
				descriptions.append(f"{ref_type}: **{ref.card.name}**")
			if descriptions:
				embed.description = "\n".join(descriptions)

		embed.set_footer(text=f"Set: {card.set.name}")

		await ctx.send(embed=embed)

	@commands.command()
	async def deck(self, ctx, deck_string):
		"""Displays the card list for the given deck
		
		Example:
		`{cmdpfx}deck ADCJWkTZX05uwGDCRV4XQGy3QGLmqUBg4GQJgGLGgO7AaABR3JlZW4vQmxhY2sgRXhhbXBsZQ__`"""
		deck_info = ParseDeck(deck_string)
		if not deck_info:
			raise UserError("This doesn't look like a proper deck string")
		cards = []
		hero_turns = {}
		card_counts = {}
		for card_info in deck_info["heroes"]:
			card = self.get_card(card_info["id"])
			for ref in card.get_references("includes"):
				deck_info["cards"].append({ "id": ref.id, "count": ref.count })
			cards.append(card)
			hero_turns[card_info["id"]] = card_info["turn"]
		for card_info in deck_info["cards"]:
			cards.append(self.get_card(card_info["id"]))
			card_counts[card_info["id"]] = card_info["count"]

		cards = list(filter(lambda c: c is not None, cards))

		embed = disnake.Embed()

		embed.title = deck_info["name"]
		embed.url = f"https://playartifact.com/d/{deck_string}"

		deck_image = await drawdota.draw_artifact_deck(deck_string, cards, hero_turns, card_counts)
		deck_image = disnake.File(deck_image, "deck.png")
		embed.set_image(url=f"attachment://{deck_image.filename}")

		await ctx.send(embed=embed, file=deck_image)



def setup(bot):
	bot.add_cog(Artifact(bot))