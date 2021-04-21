import discord
from discord.ext import commands, tasks
from sqlalchemy.sql.expression import func
from sqlalchemy import and_, or_, desc
from __main__ import settings, httpgetter
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils.commandargs import *
from cogs.utils import drawdota, imagetools
from cogs.utils import rsstools
import feedparser
import random
import os
import asyncio
import string
import re
import json
from .mangocog import *
from dotabase import *
from cogs.audio import AudioPlayerNotFoundError

session = dotabase_session()

ABILITY_KEY_MAP = {
	"q": 1,
	"w": 2,
	"e": 3,
	"d": 4,
	"f": 5,
	"r": 4 # the last ability in the list, except for invoker
}
# some specific heroes have weird places for their ultimate keys
ABILITY_ULTI_KEY_MAP = {
	"3": 4, "10": 6, "19": 4, "23": 4,
	"54": 4, "68": 4, "73": 4, "74": 6,
	"86": 6, "88": 5, "89": 4,
	"90": 4, "91": 4, "98": 5, "100": 5,
	"103": 4, "108": 4, "110": 5, "114": 6, "120": 4
}
for i in range(1, 20):
	ABILITY_KEY_MAP[str(i)] = i

# A variable that can specify a filter on a query
class QueryVariable():
	def __init__(self, name, aliases, query_filter, prefix=None):
		self.name = name
		self.aliases = aliases
		self.query_filter = query_filter
		self.prefix = prefix or ";"
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

# Filters a query for rows containing a column that contains the value in a | separated list
def query_filter_list(query, column, value, separator="|"):
	return query.filter(or_(column.like(f"%|{value}"), column.like(f"{value}|%"), column.like(f"%|{value}|%"), column.like(value)))


class Dotabase(MangoCog):
	"""For information about Dota 2, and playing hero responses

	Interfaces with [dotabase](http://github.com/mdiller/dotabase). Check out [dotabase.dillerm.io](http://dotabase.dillerm.io) if you want to see a website that interfaces with dotabase."""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.session = session
		self.criteria_aliases = read_json(settings.resource("json/criteria_aliases.json"))
		self.hero_stat_categories = read_json(settings.resource("json/hero_stats.json"))
		self.hero_aliases = {}
		self.item_aliases = {}
		self.leveled_hero_stats = [] # by level (0 is null, and 1-30 are filled in)
		self.hero_regex = ""
		self.item_regex = ""
		self.patches_regex = ""
		self.build_helpers()
		self.vpkurl = "http://dotabase.dillerm.io/dota-vpk"
		drawdota.init_dota_info(self.get_hero_infos(), self.get_item_infos(), self.get_ability_infos(), self.vpkurl)

	def build_helpers(self):
		def clean_input(t):
			return re.sub(r'[^a-z1-9\s]', r'', str(t).lower())
		for hero in session.query(Hero):
			aliases = hero.aliases.split("|")
			for alias in aliases:
				self.hero_aliases[alias] = hero.id
				self.hero_aliases[alias.replace(" ", "")] = hero.id

		patches_patterns = []
		for patch in session.query(Patch).filter(Patch.timestamp != None):
			patches_patterns.append(patch.number.replace(".", "\\."))
		self.patches_regex = f"(?:{'|'.join(patches_patterns)})"

		item_patterns = []
		for item in session.query(Item).filter(~Item.localized_name.contains("Recipe")):
			aliases = item.aliases.split("|")
			aliases.append(clean_input(item.localized_name))
			pattern = re.sub(r"[^a-z' ]", "", item.localized_name.lower())
			pattern = pattern.replace("'", "'?")
			item_patterns.append(pattern)
			for alias in aliases:
				if alias not in self.item_aliases:
					self.item_aliases[alias] = item.id
					self.item_aliases[alias.replace(" ", "")] = item.id
		self.item_regex = f"(?:{'|'.join(item_patterns)})"

		for crit in session.query(Criterion).filter(Criterion.matchkey == "Concept"):
			self.criteria_aliases[crit.name.lower()] = crit.name

		pattern_parts = {}
		for alias in self.hero_aliases:
			parts = []
			if len(alias) > 2:
				tempstring = ""
				for i in range(2, len(alias)):
					tempstring += alias[i]
					parts.append(tempstring)
			prefix = alias[:2]
			if not prefix in pattern_parts:
				pattern_parts[prefix] = []
			pattern_parts[prefix].extend(parts)
		patterns = []
		for prefix in pattern_parts:
			parts = list(set(pattern_parts[prefix]))
			parts = sorted(parts, key=lambda p: len(p), reverse=True)
			if len(parts) > 0:
				result = f"{prefix}(?:{'|'.join(parts)})?"
				patterns.append(result)
			else:
				patterns.append(prefix)
		self.hero_regex = f"(?:{'|'.join(patterns)})"


		for category in self.hero_stat_categories:
			for stat in category["stats"]:
				if "lambda" in stat:
					stat["lambda"] = eval(stat["lambda"])
		all_heroes = session.query(Hero).all()
		self.leveled_hero_stats.append(0)
		for level in range(1, 31):
			all_hero_stats = []
			for hero in all_heroes:
				hero_stats = {} #vars(hero)
				hero_stats["id"] = hero.id
				hero_stats["level"] = level
				for category in self.hero_stat_categories:
					for stat in category["stats"]:
						if "lambda" in stat:
							value = stat["lambda"](hero, hero_stats)
							hero_stats[stat["stat"]] = value
						else:
							hero_stats[stat["stat"]] = vars(hero)[stat["stat"]]
				all_hero_stats.append(hero_stats)
			self.leveled_hero_stats.append(all_hero_stats)

	def get_wiki_url(self, obj):
		if isinstance(obj, Hero):
			wikiurl = obj.localized_name
		elif isinstance(obj, Ability):
			wikiurl = f"{obj.hero.localized_name}#{obj.localized_name}"
		elif isinstance(obj, Item):
			wikiurl = obj.localized_name

		wikiurl = wikiurl.replace(" ", "_").replace("'", "%27")
		return f"http://dota2.gamepedia.com/{wikiurl}"

	def lookup_hero(self, hero):
		if not hero:
			return None
		if isinstance(hero, str):
			hero = hero.strip()
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

	def lookup_ability(self, text, full_check=True):
		if isinstance(text, str):
			text = text.strip()
		ability_query = session.query(Ability).filter(Ability.hero_id != None)
		if isinstance(text, int) or text.isdigit():
			return ability_query.filter(Ability.id == int(text)).first()
		def clean_input(t):
			return re.sub(r'[^a-z1-9\s]', r'', str(t).lower())
		text = clean_input(text)
		if text == "":
			return None
		for ability in ability_query:
			if clean_input(ability.localized_name) == text:
				return ability
		if full_check:
			for ability in ability_query:
				cleaned_name = clean_input(ability.localized_name)
				if cleaned_name.startswith(text):
					return ability
				cleaned_name = cleaned_name.replace(" ", "")
				if cleaned_name == text.replace(" ", ""):
					return ability
			for ability in ability_query:
				name = clean_input(ability.localized_name)
				if " " in name:
					for part in name.split(" "):
						if part.startswith(text):
							return ability
			for key in text.split(" "):
				if key in ABILITY_KEY_MAP:
					text = re.sub(f'\\b{key}\\b', '', text)
					hero = self.lookup_hero(text)
					if hero is None:
						return None
					ability_position = ABILITY_KEY_MAP[key]
					# use this instead of directly using ability_slot because there are some filler generic_ability things
					abilities = hero.abilities
					if ability_position > len(abilities):
						raise UserError(f"{hero.localized_name} doesn't have that many abilities")
					if key == "r": # if is ultimate and not invoker, get last ability in list
						custom_position = ABILITY_ULTI_KEY_MAP.get(str(hero.id))
						if custom_position is not None and custom_position < len(abilities):
							ability_position = custom_position
						else:
							ability_position = len(abilities)
					return abilities[ability_position - 1]
		return None

	def lookup_item(self, item, full_check=True):
		if not item:
			return None
		if isinstance(item, str):
			item = item.strip()
		item_id = self.lookup_item_id(item, full_check)
		if item_id:
			return session.query(Item).filter(Item.id == item_id).first()
		else:
			return None

	def lookup_item_id(self, text, full_check=True):
		item_query = session.query(Item)
		if "recipe" not in text.lower():
			item_query = item_query.filter(~Item.localized_name.contains("recipe"))
			item_query = item_query.filter(~Item.localized_name.contains("Recipe"))
		if isinstance(text, int) or text.isdigit():
			return int(text)
		def clean_input(t):
			return re.sub(r'[^a-z1-9\s]', r'', str(t).lower())
		text = clean_input(text)
		if text == "":
			return None
		for item in item_query:
			if clean_input(item.localized_name) == text:
				return item.id
		if text in self.item_aliases:
			return self.item_aliases[text]

		if full_check:
			for item in self.item_aliases:
				if item.startswith(text):
					return self.item_aliases[item]
			for item in self.item_aliases:
				if text in item:
					return self.item_aliases[item]
		return None

	def lookup_patch(self, patch_name):
		query = session.query(Patch).filter(Patch.number == patch_name)
		if query.count() > 0:
			return query.first()
		else:
			return None

	def lookup_nth_patch(self, n):
		query = session.query(Patch).order_by(desc(Patch.timestamp))
		if n > query.count() or n < 0:
			return None
		else:
			return query.all()[n - 1]

	def get_hero_infos(self):
		result = {}
		for hero in session.query(Hero):
			result[hero.id] = {
				"name": hero.localized_name,
				"full_name": hero.full_name,
				"icon": self.vpkurl + hero.icon,
				"attr": hero.attr_primary,
				"portrait": self.vpkurl + hero.portrait,
				"image": self.vpkurl + hero.image,
				"emoji": str(self.get_emoji(f"dota_hero_{hero.name}")),
				"roles": dict(zip(hero.roles.split("|"), map(int, hero.role_levels.split("|"))))
			}
			# role_values = list(map(int, hero.role_levels.split("|")))
			# rv_sum = sum(role_values)
			# role_values = list(map(lambda x: x / rv_sum, role_values))
			# result[hero.id]["roles"] = dict(zip(hero.roles.split("|"), role_values))
		result[0] = {
			"name": "Unknown",
			"full_name": "unknown_hero",
			"icon": self.vpkurl + "/panorama/images/heroes/icons/npc_dota_hero_antimage_png.png",
			"attr": "strength",
			"portrait": self.vpkurl + "/panorama/images/heroes/selection/npc_dota_hero_default_png.png",
			"image": self.vpkurl + "/panorama/images/heroes/npc_dota_hero_default_png.png",
			"emoji": "unknown_hero",
			"roles": {}
		}
		return result

	def get_item_infos(self):
		result = {}
		for item in session.query(Item):
			if item.icon is None:
				continue
			result[item.id] = {
				"name": item.localized_name,
				"icon": self.vpkurl + item.icon,
			}
		return result

	def get_ability_infos(self):
		result = {}
		for ability in session.query(Ability):
			if ability.icon is None:
				continue
			result[ability.id] = {
				"name": ability.localized_name,
				"icon": self.vpkurl + ability.icon,
				"slot": ability.slot,
				"entity": ability
			}
		return result

	def get_chat_wheel_infos(self):
		result = {}
		for message in session.query(ChatWheelMessage):
			result[message.id] = {
				"name": message.name,
				"message": message.message if message.message else message.name.replace("_", " ") + " (spray)",
				"is_sound": message.sound != None,
				"sound": self.vpkurl + message.sound if message.sound else None
			}
		return result

	def get_chatwheel_sound_clip(self, text):
		message = self.get_chatwheel_sound(text)
		if message:
			return f"url:{self.vpkurl}{message.sound}"
		else:
			return None

	def get_chatwheel_sound(self, text, loose_fit=False):
		def simplify(t):
			t = re.sub(r"[?!',！？.-]", "", t.lower())
			return re.sub(r"[_，]", " ", t)
		text = simplify(text)
		if text == "":
			return None
		for message in session.query(ChatWheelMessage):
			if message.sound:
				strings = list(map(simplify, [ message.name, message.message, message.label ]))
				if text in strings:
					return message
				if loose_fit:
					for string in strings:
						if text.replace(" ", "") == string.replace(" ", ""):
							return message
					for string in strings:
						if text in string:
							return message
		return None

	async def play_response(self, response, ctx):
		await self.play_clip(f"dota:{response.fullname}", ctx)

	# used for getting the right response for dota clips
	def get_response(self, responsename):
		response = session.query(Response).filter(Response.fullname == responsename).first()
		if response:
			return response
		# to support legacy clips that used name instead of fullname
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

		To search for a response without asking mangobyte, try using the [Response Searcher](http://dotabase.dillerm.io/responses/)
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
			"slark_lasthit_02"
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
		else:
			hero = self.lookup_hero(hero)
			if hero is None:
				raise UserError("Don't know what hero yer talkin about")
			query = query.filter(Response.hero_id == hero.id)
			newquery = query.filter(Response.text_simple != " its in the bag ")
			if newquery.count() > 0:
				await self.play_response_query(newquery, ctx)
			else:
				await self.play_response_query(query, ctx)

	@commands.command()
	async def chatwheel(self, ctx, *, text):
		"""Plays the given chat wheel sound

		Give the command a number between 1 and 6 to page through all of the available chat options:
		`{cmdpfx}chatwheel 1`
		`{cmdpfx}chatwheel 3`

		**Examples:**
		`{cmdpfx}chatwheel Lakad Matataaaag!`
		`{cmdpfx}chatwheel disastah`
		`{cmdpfx}chatwheel Wan Bu Liao La`
		`{cmdpfx}chatwheel 玩不了啦`
		`{cmdpfx}chatwheel ehto gg`
		`{cmdpfx}chatwheel Это ГГ`"""
		page_size = 10
		query = session.query(ChatWheelMessage).filter(ChatWheelMessage.sound.like("/%"))
		if text.isdigit():
			page = int(text)
			max_pages = int((query.count() / page_size) + 1)
			if page < 1 or page > max_pages:
				raise UserError(f"Gotta give me a number between 1 and {max_pages}")
			sounds = []
			for message in query.offset((page - 1) * page_size).limit(page_size):
				if message.sound:
					sounds.append(f"{self.get_emoji('chat_wheel_sound')} {message.message}")
			embed = discord.Embed(description="\n".join(sounds))
			embed.set_author(name=f"Chat Wheel Sounds ({page}/{max_pages})")
			await ctx.send(embed=embed)
			return

		message = self.get_chatwheel_sound(text, True)
		if message is None:
			raise UserError(f"Couldn't find chat wheel sound '{text}'")

		await self.play_clip(f"url:{self.vpkurl}{message.sound}", ctx)

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

		embed = discord.Embed(description=description)

		if hero.color:
			embed.color = discord.Color(int(hero.color[1:], 16))

		wikiurl = self.get_wiki_url(hero)

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

		base_armor = hero.base_armor + round(hero.attr_agility_base / 6.0, 1)
		embed.add_field(name="Defence", value=(
			f"{self.get_emoji('hero_armor')} {base_armor:0.1f}\n"
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

	@commands.command()
	async def talents(self, ctx, *, hero : str):
		"""Gets the talents of a specific hero

		You can give this command almost any variant of the hero's name, or the hero's id, in the same format as `{cmdpfx}hero`

		**Examples:**
		`{cmdpfx}talents shadow fiend`"""
		hero = self.lookup_hero(hero)
		if not hero:
			raise UserError("That doesn't look like a hero")

		image = await drawdota.draw_hero_talents(hero)
		image = discord.File(image, f"{hero.name}_talents.png")

		await ctx.send(file=image)


	@commands.command(aliases=["spell"])
	async def ability(self, ctx, *, ability : str):
		"""Gets information about a specific hero ability

		**Examples:**
		`{cmdpfx}ability rocket flare`
		`{cmdpfx}ability laser`
		`{cmdpfx}ability sprout`"""

		ability = self.lookup_ability(ability)

		if ability is None:
			raise UserError("I couldn't find an ability by that name")

		def format_values(values):
			values = values.split(" ")
			return " / ".join(values)

		description = ""

		ability_behavior = OrderedDict([])
		ability_behavior["channelled"] = "Channelled"
		ability_behavior["autocast"] = "Auto-Cast"
		ability_behavior["unit_target"] = "Unit Target"
		ability_behavior["point"] = "Point Target"
		ability_behavior["toggle"] = "Toggle"
		ability_behavior["aura"] = "Aura"
		ability_behavior["passive"] = "Passive"
		ability_behavior["no_target"] = "No Target"

		if ability.behavior:
			behavior = ability.behavior.split("|")
			for key in ability_behavior:
				if key in behavior:
					extra_stuff = ""
					if "aoe" in behavior:
						extra_stuff = f" (AOE)"
					description += f"**Ability:** {ability_behavior[key]}{extra_stuff}\n"
					break

		if ability.damage_type:
			damage_type = ability.damage_type[0].upper() + ability.damage_type[1:]
			description += f"**Damage Type:** {damage_type}\n"

		if ability.spell_immunity:
			spell_immunity = ability.spell_immunity[0].upper() + ability.spell_immunity[1:]
			description += f"**Pierces Spell Immunity:** {spell_immunity}\n"

		if ability.dispellable:
			dispellable = {
				"yes": "Yes",
				"no": "No",
				"yes_strong": "Strong Dispells Only"
			}[ability.dispellable]
			description += f"**Dispellable:** {dispellable}\n"


		if description != "":
			description += "\n"

		description += ability.description

		ability_special = json.loads(ability.ability_special, object_pairs_hook=OrderedDict)
		attribute_additions = [
			{
				"key": "damage",
				"header": "Damage:",
				"value": ability.damage,
				"first": True
			},
			{
				"key": "channel_time",
				"header": "Channel Time:",
				"value": ability.channel_time
			},
			{
				"key": "cast_range",
				"header": "Cast Range:",
				"value": ability.cast_range if ability.cast_range != 0 else None
			},
			{
				"key": "cast_point",
				"header": "Cast Point:",
				"value": ability.cast_point
			}
		]
		for attr in attribute_additions:
			attribute = next((x for x in ability_special if (x.get("header") and format_pascal_case(x.get("header"))) == attr["header"]), None)
			if attribute:
				attribute["first"] = attr.get("first")
				if attribute.get("value", "") == "" and attr["value"] is not None:
					attribute["value"] = attr["value"]
			else:
				if attr["value"] is not None:
					ability_special.append(attr)
		first_attr = next((x for x in ability_special if x.get("first")), None)
		if first_attr:
			ability_special.remove(first_attr)
			ability_special.insert(0, first_attr)

		formatted_attributes = []
		aghs_attributes = []
		for attribute in ability_special:
			header = attribute.get("header")
			if not header:
				continue
			header = format_pascal_case(header)

			value = attribute["value"]
			footer = attribute.get("footer")
			text = f"**{header}** {format_values(value)}"
			if footer:
				text += f" {footer}"

			if attribute.get("aghs_upgrade") and not (ability.scepter_grants or ability.shard_grants):
				aghs_attributes.append(text)
			else:
				formatted_attributes.append(text)

		if formatted_attributes:
			description += "\n\n" + "\n".join(formatted_attributes)

		# talents
		talent_query = query_filter_list(session.query(Talent), Talent.linked_abilities, ability.name)
		talents = talent_query.order_by(Talent.slot).all()
		if len(talents) > 0:
			description += f"\n\n{self.get_emoji('talent_tree')} **Talents:**"
			for talent in talents:
				description += f"\n[Level {talent.level}] {talent.localized_name}"

		# aghs scepter
		if ability.scepter_description:
			if ability.scepter_grants:
				description += f"\n\n{self.get_emoji('aghanims_scepter')} **Granted by Aghanim's Scepter**"
			else:
				description += f"\n\n{self.get_emoji('aghanims_scepter')} __**Upgradable by Aghanim's Scepter**__\n"
				description += f"*{ability.scepter_description}*\n"
				for attribute in aghs_attributes:
					description += f"\n{attribute}"

		# aghs shard
		if ability.shard_description:
			if ability.shard_grants:
				description += f"\n\n{self.get_emoji('aghanims_shard')} **Granted by Aghanim's Shard**"
			else:
				description += f"\n\n{self.get_emoji('aghanims_shard')} __**Upgradable by Aghanim's Shard**__\n"
				description += f"*{ability.shard_description}*\n"
				# for attribute in aghs_attributes:
				# 	description += f"\n{attribute}"

		embed = discord.Embed(description=description)

		embed.title = ability.localized_name
		embed.url = self.get_wiki_url(ability)

		embed.set_thumbnail(url=f"{self.vpkurl}{ability.icon}")

		if ability.cooldown and ability.cooldown != "0":
			value = format_values(ability.cooldown)
			if ability.charges:
				value += f" ({ability.charges} Charges)"
			embed.add_field(name="\u200b", value=f"{self.get_emoji('cooldown')} {value}\n")

		if ability.mana_cost and ability.mana_cost != "0":
			embed.add_field(name="\u200b", value=f"{self.get_emoji('mana_cost')} {format_values(ability.mana_cost)}\n")

		if ability.lore and ability.lore != "":
			embed.set_footer(text=ability.lore)

		await ctx.send(embed=embed)

	@commands.command()
	async def item(self, ctx, *, item : str):
		"""Gets information about a specific item

		**Examples:**
		`{cmdpfx}item shadow blade`
		`{cmdpfx}item tango`"""

		item = self.lookup_item(item)

		if item is None:
			raise UserError("I couldn't find an item by that name")

		description = ""

		if item.neutral_tier is not None:
			description += f"**Tier {item.neutral_tier}** Neutral Item\n\n"


		def format_values(values, join_string="/", base_level=None):
			if values is None:
				return None
			values = values.split(" ")
			if base_level and base_level <= len(values):
				values[base_level - 1] = f"**{values[base_level - 1]}**"
			else:
				values = map(lambda v: f"**{v}**", values)
			return join_string.join(values)

		ability_special = json.loads(item.ability_special, object_pairs_hook=OrderedDict)
		for attribute in ability_special:
			header = attribute.get("header")
			if not header:
				continue
			value = attribute["value"]
			footer = attribute.get("footer")
			text = f"{header} {format_values(value, base_level=item.base_level)}"
			if footer:
				text += f" {footer}"
			text += "\n"
			description += text


		if item.description:
			if description != "":
				description += "\n"
			description += item.description
			description += "\n"
		description = re.sub(r"(^|\n)# ([^\n]+)\n", r"\n__**\2**__\n", description)

		def clean_values(values):
			values = values.split(" ")
			return " / ".join(values)

		description += "\n"
		if item.cost and item.cost != "0":
			description += f"{self.get_emoji('gold')} {item.cost:,}\n"
		if item.mana_cost and item.mana_cost != "0":
			description += f"{self.get_emoji('mana_cost')} {clean_values(item.mana_cost)}  "
		if item.cooldown and item.cooldown != "0":
			description += f"{self.get_emoji('cooldown')} {clean_values(item.cooldown)}"

		embed = discord.Embed(description=description)

		color = drawdota.get_item_color(item)
		if color is not None:
			embed.color = discord.Color(int(color[1:], 16))


		embed.title = item.localized_name
		embed.url = self.get_wiki_url(item)

		embed.set_thumbnail(url=f"{self.vpkurl}{item.icon}")

		if item.lore and item.lore != "":
			embed.set_footer(text=item.lore)

		await ctx.send(embed=embed)


	@commands.command(aliases=["emoji"])
	async def emoticon(self, ctx, name):
		"""Gets the gif of a dota emoticon

		<a:pup:406270527766790145> <a:stunned:406274986769252353> <a:cocky:406274999951949835>

		**Examples:**
		`{cmdpfx}emoticon pup`
		`{cmdpfx}emoticon stunned`
		`{cmdpfx}emoticon naga_song`"""
		await ctx.channel.trigger_typing()

		emoticon = session.query(Emoticon).filter(Emoticon.name == name).first()

		if not emoticon:
			raise UserError(f"Couldn't find an emoticon with the name '{name}'")

		url = self.vpkurl + emoticon.url
		image = discord.File(await drawdota.create_dota_emoticon(emoticon, url), f"{name}.gif")

		await ctx.send(file=image)

	@commands.command(aliases=["addemoji"])
	async def addemoticon(self, ctx, name):
		"""Adds a dota emoticon as an animated emoji

		This command will add the dota emoticon as an animated emoji to the server. Because it is an animated emoji, only discord nitro users will be able to use it.

		Obviously, this command needs the 'Manage Emoji' permission to be able to work.

		<a:pup:406270527766790145> <a:stunned:406274986769252353> <a:cocky:406274999951949835>

		**Examples:**
		`{cmdpfx}addemoticon pup`
		`{cmdpfx}addemoticon stunned`
		`{cmdpfx}addemoticon naga_song`"""

		emoticon = session.query(Emoticon).filter(Emoticon.name == name).first()

		if not emoticon:
			raise UserError(f"Couldn't find an emoticon with the name '{name}'")

		url = self.vpkurl + emoticon.url
		image = await drawdota.create_dota_emoticon(emoticon, url)
		with open(image, 'rb') as f:
			image = f.read()

		if not ctx.guild:
			raise UserError("You have to be in a server to use this command")

		if not ctx.guild.me.guild_permissions.manage_emojis:
			raise UserError("An admin needs to give me the 'Manage Emojis' permission before I can do that")

		await ctx.guild.create_custom_emoji(name=name, image=image, reason=f"Dota emoji created for {ctx.message.author.name}")

		await ctx.message.add_reaction("✅")

	@commands.command()
	async def lore(self, ctx, *, name=None):
		"""Gets the lore of a hero, ability, or item

		Returns a random piece of lore if no name is specified

		**Examples:**
		`{cmdpfx}lore bristleback`
		`{cmdpfx}lore shadow blade`
		`{cmdpfx}lore venomous gale`"""
		lore_info = {}
		found = False

		if name is None:
			# Randomize!
			names = []
			for item in session.query(Item).filter(Item.lore != ""):
				names.append(item.localized_name)
			for ability in session.query(Ability).filter(Ability.lore != ""):
				names.append(ability.localized_name)
			for hero in session.query(Hero).filter(Hero.bio != ""):
				names.append(hero.localized_name)
			name = random.choice(names)

		item = self.lookup_item(name, False)
		if item:
			found = True
			lore_info = {
				"name": item.localized_name,
				"icon": item.icon,
				"lore": item.lore,
				"object": item
			}

		if not found:
			ability = self.lookup_ability(name, False)
			if ability:
				found = True
				lore_info = {
					"name": ability.localized_name,
					"icon": ability.icon,
					"lore": ability.lore,
					"object": ability
				}

		if not found:
			hero = self.lookup_hero(name)
			if hero:
				found = True
				lore_info = {
					"name": hero.localized_name,
					"icon": hero.portrait,
					"lore": hero.bio,
					"object": hero
				}

		if not found:
			raise UserError("I Couldn't find an ability hero or item by that name")

		if lore_info["lore"] == "":
			raise UserError("There is no in-game lore for that")


		lore_text = lore_info["lore"]
		maxlen = 1950
		if len(lore_text) > maxlen:
			lore_text = lore_text[:maxlen] + "..."
		embed = discord.Embed(description=lore_text)

		embed.title = lore_info["name"]
		embed.url = self.get_wiki_url(lore_info["object"])

		if lore_info["icon"]:
			embed.set_thumbnail(url=f"{self.vpkurl}{lore_info['icon']}")

		await ctx.send(embed=embed)

	@commands.command(aliases=["aghs", "ags", "aghanims", "scepter", "shard"])
	async def aghanim(self, ctx, *, name):
		"""Gets the aghs upgrade for the given hero or ability"""
		abilities = []
		hero = self.lookup_hero(name)
		if hero:
			for ability in hero.abilities:
				if ability.scepter_upgrades or ability.shard_upgrades or ability.scepter_grants or ability.shard_grants:
					abilities.append(ability)

			if len(abilities) == 0:
				raise UserError(f"Couldn't find an aghs upgrade for {hero.localized_name}. Either they don't have one or I just can't find it.")
		else:
			ability = self.lookup_ability(name, True)
			if not ability:
				raise UserError("Couldn't find a hero or ability by that name")
			if not ability.aghanim:
				raise UserError(f"Looks like {ability.localized_name} doesn't have an aghs upgrade")
			abilities = [ ability ]

		item_shard = self.lookup_item("aghanim's shard")
		item_scepter = self.lookup_item("aghanim's scepter")
		for upgrade_type in [ "scepter", "shard" ]:
			aghs_item = item_scepter
			icon_url = f"{self.vpkurl}/panorama/images/hud/reborn/aghsstatus_scepter_on_psd.png"
			if upgrade_type == "shard":
				aghs_item = item_shard
				icon_url = f"{self.vpkurl}/panorama/images/hud/reborn/aghsstatus_shard_on_psd.png"
			for ability in abilities:
				description = ability.scepter_description if upgrade_type == "scepter" else ability.shard_description
				is_grantedby = ability.scepter_grants if upgrade_type == "scepter" else ability.shard_grants
				if description != "":
					if is_grantedby:
						description = f"**{description}**\n\n*{ability.description}*"
					else:
						description = f"*{description}*\n"

				ability_special = json.loads(ability.ability_special, object_pairs_hook=OrderedDict)
				formatted_attributes = []
				if upgrade_type == "scepter" and ability.scepter_upgrades and not ability.scepter_grants:
					for attribute in ability_special:
						header = attribute.get("header")
						if not (header and attribute.get("aghs_upgrade")):
							continue
						header = format_pascal_case(header)
						value = attribute["value"]
						footer = attribute.get("footer")
						value = " / ".join(value.split(" "))
						text = f"**{header}** {value}"
						if footer:
							text += f" {footer}"
						if description != "":
							description += "\n"
						description += f"{text}"

				if description == "":
					continue
				embed = discord.Embed(description=description)
				title = f"{aghs_item.localized_name} ({ability.localized_name})"
				embed.set_author(name=title, icon_url=icon_url)
				embed.set_thumbnail(url=f"{self.vpkurl}{ability.icon}")
				await ctx.send(embed=embed)

	@commands.command(aliases=["recipes", "craft", "crafting"])
	async def recipe(self, ctx, *, item):
		"""Shows the recipes involving this item"""
		item = self.lookup_item(item, True)
		if not item:
			raise UserError("Can't find an item by that name")

		products = query_filter_list(session.query(Item), Item.recipe, item.name).all()
		components = []
		if item.recipe:
			component_names = item.recipe.split("|")
			found_components = session.query(Item).filter(Item.name.in_(component_names)).all()
			for name in component_names:
				for component in found_components:
					if component.name == name:
						components.append(component)
						break


		embed = discord.Embed()

		embed.description = f"**Total Cost:** {self.get_emoji('gold')} {item.cost}"

		if components:
			value = ""
			for i in components:
				value += f"{i.localized_name} ({self.get_emoji('gold')} {i.cost})\n"
			embed.add_field(name="Created from", value=value)
		if products:
			value = ""
			for i in products:
				value += f"{i.localized_name} ({self.get_emoji('gold')} {i.cost})\n"
			embed.add_field(name="Can be made into", value=value)

		title = item.localized_name
		if len(products) > 1 or (components and products):
			title += " (Recipes)"
		else:
			title += " (Recipe)"

		embed.title = title
		embed.url = self.get_wiki_url(item)

		color = drawdota.get_item_color(item)
		if color is not None:
			embed.color = discord.Color(int(color[1:], 16))

		image = discord.File(await drawdota.draw_itemrecipe(item, components, products), "recipe.png")
		embed.set_image(url=f"attachment://{image.filename}")

		await ctx.send(embed=embed, file=image)



	@commands.command(aliases=["fuse", "fuze", "fuzeheroes"])
	async def fuseheroes(self, ctx, *, heroes=None):
		"""See what would happen if you fused two heroes together

		If no heroes are given, two will be chosen at random

		**Example:**
		`{cmdpfx}fuseheroes axe chen`"""
		await ctx.channel.trigger_typing()
		if heroes is None:
			heroes = session.query(Hero).order_by(func.random()).limit(2).all()
			heroes = " ".join(map(lambda h: h.localized_name, heroes))

		words = heroes.split(" ")

		hero1 = None
		hero2 = None
		for i in range(1, len(words)):
			hero1 = self.lookup_hero(" ".join(words[:i]))
			hero2 = self.lookup_hero(" ".join(words[i:]))
			if hero1 and hero2:
				break

		if not (hero1 and hero2):
			raise UserError("That doesn't look like two distinct heroes")
		if hero1.id == hero2.id:
			raise UserError("Fusing something with itself sounds boring")

		def combine_words(word1, word2):
			middle1 = len(word1) - (len(word1) // 2)
			middle2 = len(word2) - (len(word2) // 2)
			return word1[:middle1] + word2[middle2:]

		name1 = hero1.localized_name
		name2 = hero2.localized_name
		if " " not in name1 and " " not in name2:
			hero_name = combine_words(name1, name2)
		if " " in name1 and " " not in name2:
			hero_name = name1.split(" ")[0] + " " + name2
		if " " not in name1 and " " in name2:
			hero_name = name1 + " " + name2.split(" ")[-1]
		if " " in name1 and " " in name2:
			hero_name = name1.split(" ")[0] + " " + name2.split(" ")[-1]
			if hero_name == name1 or hero_name == name2:
				hero_name = combine_words(name1.split(" ")[0], name2.split(" ")[0]) + " " + name2.split(" ")[-1]
			if hero_name == name1 or hero_name == name2:
				hero_name = name1.split(" ")[0] + " " + combine_words(name1.split(" ")[-1], name2.split(" ")[-1])


		embed = discord.Embed()

		embed.title = hero_name

		emoji1 = self.get_emoji(f"dota_hero_{hero1.name}")
		emoji2 = self.get_emoji(f"dota_hero_{hero2.name}")

		embed.description = f"{emoji1} + {emoji2}"

		color1 = imagetools.Color(hero1.color)
		color2 = imagetools.Color(hero2.color)
		color = color1.blend(color2)
		embed.color = discord.Color(color.integer)

		image = discord.File(await drawdota.fuse_hero_images(hero1, hero2), "hero.png")
		embed.set_thumbnail(url=f"attachment://{image.filename}")

		await ctx.send(embed=embed, file=image)


	@commands.command()
	async def courage(self, ctx, *, hero = None):
		"""Generates a challenge build

		Creates a challenge build with a random (or given) hero and a random set of items

		**Examples:**
		`{cmdpfx}courage`
		`{cmdpfx}courage shadow fiend`"""

		all_boots = [
			"travel_boots",
			"phase_boots",
			"power_treads",
			"arcane_boots",
			"tranquil_boots",
			"guardian_greaves"
		]

		random.seed(datetime.now())
		all_items = read_json(settings.resource("json/courage_items.json"))
		random.shuffle(all_items)
		items = all_items[0:5]
		items.append(random.choice(all_boots))
		random.shuffle(items)

		item_ids = []
		for item in items:
			item_ids.append(session.query(Item).filter(Item.name == f"item_{item}").first().id)
		if hero:
			hero_id = self.lookup_hero_id(hero)
			if not hero_id:
				raise UserError(f"Couldn't a hero called '{hero}'")
		else:
			hero_id = session.query(Hero).order_by(func.random()).first().id

		image = discord.File(await drawdota.draw_courage(hero_id, item_ids), "courage.png")
		await ctx.send(file=image)


	@commands.command(aliases=["neutrals", "neutraltier"])
	async def neutralitems(self, ctx, *, tier = None):
		"""Displays all of the neutral items

		If a tier is specified, display the items in that tier, along with their names

		`{cmdpfx}neutralitems`
		`{cmdpfx}neutralitems tier 5`
		`{cmdpfx}neutralitems 3`"""

		if tier is not None:
			tier = tier.lower().replace("tier", "").replace("t", "").strip()
			if not tier.isdigit():
				raise UserError("Please specify a tier like 'tier 5'")
			tier = int(tier)
			if tier < 1 or tier > 5:
				raise UserError("Please specify a tier between 1 and 5")

		embed = discord.Embed()

		title = "Neutral Items"
		if tier is not None:
			title = f"Tier {tier} Neutral Items"
		embed.title = title
		embed.url = "https://dota2.gamepedia.com/Neutral_Items"

		all_neutral_items = session.query(Item).filter(Item.neutral_tier != None).filter(Item.recipe == None).order_by(Item.localized_name).all()
		image = discord.File(await drawdota.draw_neutralitems(tier, all_neutral_items), "neutralitems.png")
		embed.set_image(url=f"attachment://{image.filename}")
		if tier is not None:
			tier_color = drawdota.neutral_tier_colors[str(tier)]
			embed.color = discord.Color(int(tier_color[1:], 16))

		if tier is None:
			embed.set_footer(text="Also try: ?neutralitems tier 4")
		await ctx.send(embed=embed, file=image)

	@commands.command(aliases=["startingstats", "tradingstats", "lvlstats", "lvledstats"])
	async def leveledstats(self, ctx, *, hero : str):
		"""Gets the stats for a hero at the specified level

		If no level is specified, get the stats for the hero at level 1

		**Examples:**
		`{cmdpfx}leveledstats tinker`
		`{cmdpfx}leveledstats shaker lvl 2`
		`{cmdpfx}leveledstats level 28 shaman`"""
		lvl_regex = r"(?:(max) (?:lvl|level)|(?:lvl|level)? ?(\d+))"
		match = re.search(lvl_regex, hero, re.IGNORECASE)
		level = 1
		if match:
			if match.group(1):
				level = 30
			else:
				level = int(match.group(2))
			if level < 1 or level > 30:
				raise UserError("Please enter a level between 1 and 30")
			hero = re.sub(lvl_regex, "", hero)

		hero = self.lookup_hero(hero)
		if not hero:
			raise UserError("That doesn't look like a hero")

		stat_category = next((c for c in self.hero_stat_categories if c["section"] == "Combat Stats"), None)["stats"]

		description = ""
		hero_stats = next((h for h in self.leveled_hero_stats[level] if h["id"] == hero.id), None)

		for stat in stat_category:
			name = stat["name"]
			value = hero_stats[stat["stat"]]
			if stat.get("display") == "resistance_percentage":
				value = 100 * (1 - value)
			if stat.get("display") == "int":
				value = round(value)
			value = f"{value:.2f}"
			value = re.sub("\.0+$", "", value)
			if stat.get("display") == "resistance_percentage":
				value += "%"
			description += f"\n{name}: **{value}**"

		embed = discord.Embed(description=description)

		title = f"Level {level} {hero.localized_name}"
		embed.set_author(name=title, icon_url=f"{self.vpkurl}{hero.icon}")
		embed.set_thumbnail(url=f"{self.vpkurl}{hero.portrait}")
		if hero.color:
			embed.color = discord.Color(int(hero.color[1:], 16))
		embed.set_footer(text="The stats shown above do not account for talents, passives, or items")

		await ctx.send(embed=embed)

	@commands.command(aliases=["statstable", "stattable", "heroestable", "leveledstatstable", "besthero", "bestheroes"])
	async def herotable(self, ctx, *, table_args : HeroStatsTableArgs):
		"""Displays a sorted table of heroes and their stats

		Displays a table with computed hero stats showing which heroes have the highest values for the specified stat. To see the list of possible stats, try the `{cmdpfx}leveledstats` command

		**Examples:**
		`{cmdpfx}herotable dps`
		`{cmdpfx}herotable health lvl 30`
		`{cmdpfx}herotable attack speed level 21 descending`
		"""
		if table_args.stat is None:
			raise UserError(f"Please select a stat to sort by. For a list of stats, see `{self.cmdpfx()}leveledstats`")
		if table_args.hero_level < 1 or table_args.hero_level > 30:
			raise UserError("Please select a hero level between 1 and 30")
		if table_args.hero_count < 2 or table_args.hero_count > 40:
			raise UserError("Please select a hero count between 2 and 40")

		embed = discord.Embed()

		image = discord.File(await drawdota.draw_herostatstable(table_args, self.hero_stat_categories, self.leveled_hero_stats), "herotable.png")
		embed.set_image(url=f"attachment://{image.filename}")
		embed.set_footer(text="The stats shown above do not account for talents, passives, or items")

		await ctx.send(embed=embed, file=image)

	@commands.command(aliases=["spells"])
	async def abilities(self, ctx, *, hero):
		"""Shows all of the abilities/spells for that hero"""
		hero = self.lookup_hero(hero)
		if not hero:
			raise UserError("That doesn't look like a hero")

		abilities = []
		for ability in list(filter(lambda a: a.slot is not None, hero.abilities)):
			if not hero.id == 74: # invoker
				if "hidden" in ability.behavior and not (ability.shard_grants or ability.scepter_grants):
					continue
			abilities.append(ability)

		embed = discord.Embed()

		embed.title = hero.localized_name
		embed.url = self.get_wiki_url(hero)

		image = discord.File(await drawdota.draw_heroabilities(abilities), "abilities.png")
		embed.set_image(url=f"attachment://{image.filename}")

		embed.color = discord.Color(int(hero.color[1:], 16))

		await ctx.send(embed=embed, file=image)


	@commands.command(aliases = ["rss"])
	async def blog(self,ctx):
		""" Pulls the newest blog post for Dota 2"""
		await ctx.send("Sorry, Valve broke this for now.")
		return # return cuz valve broke it
		feed = await httpgetter.get(r'https://blog.dota2.com/feed', return_type="text")
		blog = feedparser.parse(feed)
		title = "Dota 2 Blog"
		embed = rsstools.create_embed(title, blog.entries[0])
		await ctx.send(embed = embed)

	@tasks.loop(minutes=5)
	async def check_dota_blog(self):
		feed = await httpgetter.get(r'https://blog.dota2.com/feed', return_type="text")
		blog = feedparser.parse(feed)
		title = "Dota 2 Blog"

		updated = rsstools.is_new_blog(blog.entries[0])
		if not updated: #if its not updated, stop here
			return

		embed = rsstools.create_embed(title, blog.entries[0]) #generate embed

		##next section copies code in check_dota_patch in general cogs
		messageables = []
		#find channels to post in
		guildinfos = botdata.guildinfo_list()
		for guildinfo in guildinfos:
			if guildinfo.dotablogchannel is not None:
				channel = self.bot.get_channel(guildinfo.dotablogchannel)
				if channel is not None:
					messageables.append(channel)
				else:
					print(f"couldn't find channel {guildinfo.dotablogchannel} when announcing dota blog")

		#find users
		userinfos = botdata.userinfo_list()
		for userinfo in userinfos:
			if userinfo.dmdotablog:
				user = self.bot.get_user(userinfo.discord)
				if user is not None:
					messageables.append(user)
				else:
					print(f"couldn't find user {userinfo.discord} when announcing dota blog")

		#bundle tasks and execute
		tasks = []
		for messageable in messageables:
			tasks.append(messageable.send(embed=embed))

		bundler = AsyncBundler(tasks)
		await bundler.wait()


def setup(bot):
	bot.add_cog(Dotabase(bot))
