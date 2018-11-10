import discord
from discord.ext import commands
from __main__ import settings, botdata, httpgetter
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
import random
import os
import re


class Artifact(MangoCog):
	"""Artifact related commands
	
	A few commands providing information about Valve's new game [Artifact](https://playartifact.com)"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.cards_uri = "artifact_cards"
		self.sets_uri = "artifact_sets"
		self.card_sets = []
		self.cards = []

	async def load_card_sets(self):
		sets_filename = httpgetter.cache.get_filename(self.sets_uri)
		cards_filename = httpgetter.cache.get_filename(self.cards_uri)

		if cards_filename is None or sets_filename is None:
			await self.update_card_sets()
			return

		self.card_sets = read_json(sets_filename)
		self.cards = read_json(cards_filename)
		self.card_names = OrderedDict()
		for card in self.cards:
			if card["card_name"] and card["card_name"]["english"]:
				name = card["card_name"]["english"].lower()
				self.card_names[name] = card["card_id"]

	async def update_card_sets(self):
		sets_data = []
		cards_data = []
		for n in range(0, 100):
			try:
				set_data = await httpgetter.get(f"https://playartifact.com/cardset/{str(n).zfill(2)}")
			except HttpError as e:
				if e.code == 400:
					break # this set doesnt exist yet
				else:
					raise
			data = (await httpgetter.get(f"{set_data['cdn_root']}{set_data['url']}"))["card_set"]
			new_set_data = OrderedDict()
			new_set_data["id"] = data["set_info"]["set_id"]
			new_set_data["version"] = data["version"]
			new_set_data["name"] = data["set_info"]["name"]["english"]
			sets_data.append(new_set_data)
			set_id = new_set_data["id"]

			for new_card_data in data["card_list"]:
				new_card_data["set_id"] = set_id
				cards_data.append(new_card_data)

		sets_filename = await httpgetter.cache.new(self.sets_uri, "json")
		write_json(sets_filename, sets_data)

		cards_filename = await httpgetter.cache.new(self.cards_uri, "json")
		write_json(cards_filename, cards_data)

		await self.load_card_sets()

	def clean_text(self, text):
		text = re.sub(r"<span [^>]+>([^<])</span>", r"**\1**", text)
		text = re.sub(r"<BR>", "\n", text)
		return text

	def get_card_color(self, card):
		if card.get("is_green"):
			return discord.Color(0x59753f)
		if card.get("is_red"):
			return discord.Color(0x942e38)
		if card.get("is_blue"):
			return discord.Color(0x225c7c)
		if card.get("is_black"):
			return discord.Color(0x312a2d)
		if card.get("card_type") == "Item":
			return discord.Color(0xdf9a3b)
		else:
			return discord.Color(0x706c67)

	def get_card(self, card_id):
		for card in self.cards:
			if card["card_id"] == card_id:
				return card
		return None

	def find_card(self, name):
		if name is None:
			return random.choice(self.cards)
		name = name.lower()
		for card_name in self.card_names:
			if name == card_name:
				return self.get_card(self.card_names[card_name])
		for card_name in self.card_names:
			if name in card_name:
				return self.get_card(self.card_names[card_name])
		pattern = r"[^a-z]"
		name = re.sub(pattern, "", name)
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


	@commands.command(aliases=["card"])
	async def artifact(self, ctx, *, card_name : str=None):
		"""Displays info about the artifact card

		
		Example:
		`{cmdpfx}artifact Healing Salve`
		`{cmdpfx}artifact Prowler Vanguard`
		`{cmdpfx}artifact keefe`"""
		card = self.find_card(card_name)

		if card is None:
			raise UserError(f"Couldn't find any card with the name '{card_name}'")

		embed = discord.Embed(color=self.get_card_color(card))
		if card["mini_image"]:
			embed.set_author(name=card["card_name"]["english"], icon_url=card["mini_image"]["default"])
		else:
			embed.set_author(name=card["card_name"]["english"])
		
		if card["large_image"]:
			embed.set_image(url=card["large_image"]["default"])
		elif card["card_text"]:
			embed.description = self.clean_text(card["card_text"]["english"])

		if card.get("references"):
			descriptions = []
			for ref in card.get("references"):
				ref_type = format_pascal_case(ref["ref_type"].replace("_", " "))
				if ref.get("count"):
					ref_type += f" (x{ref['count']})"
				ref_card = self.get_card(ref["card_id"])
				descriptions.append(f"**{ref_type}:** {ref_card['card_name']['english']}")
			if descriptions:
				embed.description = "\n".join(descriptions)


		set_name = next((card_set for card_set in self.card_sets if card_set["id"] == card["set_id"]), None)["name"]
		embed.set_footer(text=f"Set: {set_name}")

		await ctx.send(embed=embed)


def setup(bot):
	bot.add_cog(Artifact(bot))