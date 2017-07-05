import discord
from discord.ext import commands
from sqlalchemy.sql.expression import func
from sqlalchemy import and_, or_
from __main__ import settings
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import drawdota
import random
import os
import asyncio
import string
import re
from .mangocog import *
from dotabase import *
from cogs.audio import AudioPlayerNotFoundError

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
	"""Dota hero responses and info

	Interfaces with [dotabase](http://github.com/mdiller/dotabase). Check out [dotabase.me](http://dotabase.me) if you want to see a website that interfaces with dotabase."""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.session = session
		self.criteria_aliases = read_json(settings.resource("json/criteria_aliases.json"))
		self.hero_aliases = {}
		self.build_aliases()
		self.vpkurl = "http://dotabase.me/dota-vpk"
		drawdota.init_dota_info(self.get_hero_infos(), self.get_item_infos())

	def build_aliases(self):
		for hero in session.query(Hero):
			aliases = hero.aliases.split("|")
			for alias in aliases:
				self.hero_aliases[alias] = hero.id
				self.hero_aliases[alias.replace(" ", "")] = hero.id

		for crit in session.query(Criterion).filter(Criterion.matchkey == "Concept"):
			self.criteria_aliases[crit.name.lower()] = crit.name

	def lookup_hero(self, hero):
		if not hero:
			return None
		hero_id = self.lookup_hero_id(hero)
		if hero_id:
			return session.query(Hero).filter(Hero.id == hero_id).first()
		else:
			return None

	def lookup_hero_id(self, text):
		if isinstance(text, int) or text.isdigit():
			query = session.query(Hero).filter(Hero.id == int(text))
			return int(text) if query.count() > 0 else None
		text = re.sub(r'[^a-z^\s]', r'', text.lower())
		if text == "":
			return None
		if text in self.hero_aliases:
			return self.hero_aliases[text]
		for hero in session.query(Hero):
			if hero.localized_name.lower().startswith(text):
				return hero.id
		for hero in self.hero_aliases:
			if hero.startswith(text):
				return self.hero_aliases[hero]
		for hero in self.hero_aliases:
			if text in hero:
				return self.hero_aliases[hero]
		return None

	def get_hero_infos(self):
		result = {}
		for hero in session.query(Hero):
			result[hero.id] = {
				"name": hero.localized_name,
				"full_name": hero.full_name,
				"icon": self.vpkurl + hero.icon,
				"attr": hero.attr_primary,
				"portrait": self.vpkurl + hero.portrait,
				"image": self.vpkurl + hero.image
			}
		return result

	def get_item_infos(self):
		result = {}
		for item in session.query(Item):
			result[item.id] = {
				"name": item.localized_name,
				"icon": self.vpkurl + item.icon,
			}
		return result

	def get_chat_wheel_infos(self):
		result = {}
		for message in session.query(ChatWheelMessage):
			result[message.id] = {
				"name": message.name,
				"message": message.message,
				"is_sound": message.sound != None,
			}
		return result

	async def play_response(self, response, ctx):
		await self.play_clip("dota:" + response.name, ctx)

	def get_response(self, responsename):
		return session.query(Response).filter(Response.name == responsename).first()

	# Plays a random response from a query
	async def play_response_query(self, query, ctx):
		await self.play_response(query.order_by(func.random()).first(), ctx)

	@commands.command(aliases=["dotar"])
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
		query = await self.dota_keyphrase_query(keyphrase)

		if query is None:
			await ctx.send("No responses found! 😱")
		else:
			await self.play_response_query(query, ctx)


	async def dota_keyphrase_query(self, keyphrase):
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

		return query


	async def smart_dota_query(self, words, variables, exact=False):
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

		simple_input = " " + re.sub(r'[^a-z0-9\s]', r'', keyphrase.lower()) + " "

		query = basequery.filter(Response.text_simple == simple_input)
		if query.count() > 0:
			return query

		if not exact:
			query = basequery.filter(Response.text_simple.like("%" + simple_input + "%"))
			if query.count() > 0:
				return query

		return None

	@commands.command(aliases=["hi"])
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
		await self.play_response(response, ctx)

	# Plays the correct command for the given keyphrase and hero, if a valid one is given
	async def hero_keyphrase_command(self, keyphrase, hero, ctx):
		query = await self.dota_keyphrase_query(keyphrase)
		if hero is None:
			await self.play_response_query(query, ctx)
			return

		hero = self.lookup_hero(hero)
		if hero is None:
			raise UserError("Don't know what hero yer talkin about")
		else:
			query = query.filter(Response.hero_id == hero.id)
			if query.count() > 0:
				await self.play_response_query(query, ctx)
			else:
				raise UserError(f"No responses found for {hero.localized_name}! 😱")

	@commands.command(aliases=["nope"])
	async def no(self, ctx, *, hero=None):
		"""Nopes."""
		await self.hero_keyphrase_command("no", hero, ctx)

	@commands.command()
	async def yes(self, ctx, *, hero=None):
		"""Oooooh ya."""
		await self.hero_keyphrase_command("yes", hero, ctx)

	@commands.command(aliases=["laugh", "haha", "lerl"])
	async def lol(self, ctx, *, hero=None):
		"""WOW I WONDER WAT THIS DOES

		Laughs using dota. Thats what it does."""
		await self.hero_keyphrase_command(";laugh", hero, ctx)

	@commands.command(aliases=["ty"])
	async def thanks(self, ctx, *, hero=None):
		"""Gives thanks

		Thanks are given by a random dota hero in their own special way"""
		await self.hero_keyphrase_command(";thanks", hero, ctx)

	@commands.command()
	async def inthebag(self, ctx, *, hero=None):
		"""Proclaims that 'IT' (whatever it is) is in the bag"""
		query = await self.dota_keyphrase_query(";inthebag")
		if hero is None:
				await self.play_response_query(query.filter(Response.text_simple != " its in the bag "), ctx)
		elif hero in self.hero_aliases:
			query = query.filter(Response.hero_id == self.hero_aliases[hero])
			newquery = query.filter(Response.text_simple != " its in the bag ")
			if newquery.count() > 0:
				await self.play_response_query(newquery, ctx)
			else:
				await self.play_response_query(query, ctx)
		else:
			raise UserError("Don't know what hero yer talkin about")


	@commands.command()
	async def hero(self, ctx, *, hero : str):
		"""Gets information about a specific hero

		You can give this command almost any variant of the hero's name, or the hero's id

		**Examples:**
		`{cmdpfx}hero sf`
		`{cmdpfx}hero inker`
		`{cmdpfx}hero furi`"""
		hero = self.lookup_hero(hero)
		if not hero:
			raise UserError("That doesn't look like a hero")

		description = ""
		def add_attr(name, base_func, gain_func):
			global description
			result = f"{base_func(hero)} + {gain_func(hero)}"
			if hero.attr_primary == name:
				result = f"**{result}**"
			icon = self.get_emoji(f"attr_{name}")
			return f"{icon} {result}\n"

		description += add_attr("strength", lambda h: h.attr_strength_base, lambda h: h.attr_strength_gain)
		description += add_attr("agility", lambda h: h.attr_agility_base, lambda h: h.attr_agility_gain)
		description += add_attr("intelligence", lambda h: h.attr_intelligence_base, lambda h: h.attr_intelligence_gain)

		if hero.glow_color:
			embed = discord.Embed(description=description, color=discord.Color(int(hero.glow_color[1:], 16)))
		else:
			embed = discord.Embed(description=description)

		wikiurl = hero.localized_name.replace(" ", "_").replace("'", "%27")
		wikiurl = f"http://dota2.gamepedia.com/{wikiurl}"

		embed.set_author(name=hero.localized_name, icon_url=f"{self.vpkurl}{hero.icon}", url=wikiurl)
		embed.set_thumbnail(url=f"{self.vpkurl}{hero.portrait}")

		base_damage = {
			"strength": hero.attr_strength_base,
			"agility": hero.attr_agility_base,
			"intelligence": hero.attr_intelligence_base
		}[hero.attr_primary]

		attack_stats = (
			f"{self.get_emoji('hero_damage')} {base_damage + hero.attack_damage_min} - {base_damage + hero.attack_damage_max}\n"
			f"{self.get_emoji('hero_attack_rate')} {hero.attack_rate}\n"
			f"{self.get_emoji('hero_attack_range')} {hero.attack_range}\n")
		if not hero.is_melee:
			attack_stats += f"{self.get_emoji('hero_projectile_speed')} {hero.attack_projectile_speed:,}\n"
		embed.add_field(name="Attack", value=attack_stats)


		embed.add_field(name="Defence", value=(
			f"{self.get_emoji('hero_armor')} {hero.base_armor + round(hero.attr_agility_base / 7, 1):0.1f}\n"
			f"{self.get_emoji('hero_magic_resist')} {hero.magic_resistance}%\n"))

		embed.add_field(name="Mobility", value=(
			f"{self.get_emoji('hero_speed')} {hero.base_movement}\n"
			f"{self.get_emoji('hero_turn_rate')} {hero.turn_rate}\n"
			f"{self.get_emoji('hero_vision_range')} {hero.vision_day:,} / {hero.vision_night:,}\n"))

		if hero.real_name != '':
			embed.add_field(name="Real Name", value=hero.real_name)

		roles = hero.roles.split("|")
		embed.add_field(name=f"Role{'s' if len(roles) > 1 else ''}", value=', '.join(roles))

		await ctx.send(embed=embed)

		query = session.query(Response).filter(Response.hero_id == hero.id).filter(or_(Response.criteria.like("Spawn %"), Response.criteria.like("Spawn%")))
		if query.count() > 0:
			try:
				await self.play_response_query(query, ctx)
			except AudioPlayerNotFoundError:
				pass

		


def setup(bot):
	bot.add_cog(Dotabase(bot))