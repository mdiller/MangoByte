from ast import Or
import json
import random
import re
from textwrap import indent

import disnake
import feedparser
import utils.drawing.dota as drawdota
import utils.drawing.imagetools as imagetools
import utils.other.rsstools as rsstools
from disnake.ext import commands, tasks
from sqlalchemy import and_, desc, or_
from sqlalchemy.sql.expression import func
from sqlalchemy.orm.collections import InstrumentedList
from utils.command.clip import *
from utils.command.commandargs import *
from utils.tools.globals import httpgetter, logger, settings
from utils.tools.helpers import *
from typing import TypeVar

from cogs.audio import AudioPlayerNotFoundError, Audio
from dotabase import *

from cogs.mangocog import *

CRITERIA_ALIASES = read_json(settings.resource("json/criteria_aliases.json"))
DOTA_LANG_MAP = read_json(settings.resource("json/dota_lang_map.json"))

session = dotabase_session()

CURRENT_DOTA_PATCH_NUMBER = session.query(Patch).order_by(desc(Patch.timestamp)).first().number

T = TypeVar('T')
class LocaleWrapper():
	def __init__(self, object, locale):
		self.object = object
		self.locale = locale

	def __getattr__(self, name):
		if not hasattr(self.object, name):
			return None
		if hasattr(self.object, "strings"):
			for string in self.object.strings:
				if string.lang == self.locale and string.column == name:
					return string.value
		result = getattr(self.object, name)
		if isinstance(result, Base):
			return LocaleWrapper(result, self.locale)
		if isinstance(result, InstrumentedList):
			return list(map(lambda o: LocaleWrapper(o, self.locale), result))
		return result
	
	@classmethod
	def wrap(cls, inter: disnake.CmdInter, object: T) -> T:
		if object is None or isinstance(object, LocaleWrapper):
			return object
		lang = DOTA_LANG_MAP.get(inter.locale.name, None)
		if not lang:
			lang = "english"
		return LocaleWrapper(object, lang)

ABILITY_KEY_MAP = {
	"q": 1,
	"w": 2,
	"e": 3,
	"d": 4,
	"f": 5,
	"r": 4 # the last ability in the list, except for invoker
}
for i in range(1, 20):
	ABILITY_KEY_MAP[str(i)] = i
	
# registers the method as the custom converter for that class
def register_custom_converter(cls, method):
	commands.ParamInfo._registered_converters[cls] = method
	cls.__discord_converter__ = method

async def convert_hero(inter: disnake.CmdInter, text: str) -> Hero:
	dota_cog: Dotabase
	dota_cog = inter.bot.get_cog("Dotabase")
	hero = dota_cog.lookup_hero(text)
	if hero is None:
		raise CustomBadArgument(UserError(f"Couldn't find a hero called '{text}'"))
	hero = LocaleWrapper.wrap(inter, hero)
	return hero
register_custom_converter(Hero, convert_hero)

async def convert_item(inter: disnake.CmdInter, text: str) -> Item:
	dota_cog: Dotabase
	dota_cog = inter.bot.get_cog("Dotabase")
	item = dota_cog.lookup_item(text)
	if item is None:
		raise CustomBadArgument(UserError(f"Couldn't find a item called '{text}'"))
	item = LocaleWrapper.wrap(inter, item)
	return item
register_custom_converter(Item, convert_item)

async def convert_ability(inter: disnake.CmdInter, text: str) -> Ability:
	dota_cog: Dotabase
	dota_cog = inter.bot.get_cog("Dotabase")
	ability = dota_cog.lookup_ability(text)
	if ability is None:
		raise CustomBadArgument(UserError(f"Couldn't find a ability called '{text}'"))
	ability = LocaleWrapper.wrap(inter, ability)
	return ability
register_custom_converter(Ability, convert_ability)

# setup enum for hero stat
HERO_STAT_ENUM = OrderedDict()
for category in read_json(settings.resource("json/hero_stats.json")):
	for stat in category["stats"]:
		HERO_STAT_ENUM[stat["name"]] = stat["stat"]
HERO_STAT_ENUM = commands.option_enum(HERO_STAT_ENUM)

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


# Filters a query for rows containing a column that contains the value in a | separated list
def query_filter_list(query, column, value, separator="|"):
	return query.filter(or_(column.like(f"%|{value}"), column.like(f"{value}|%"), column.like(f"%|{value}|%"), column.like(value)))


class Dotabase(MangoCog):
	"""For information about the game Dota 2 [Patch **{CURRENT_DOTA_PATCH_NUMBER}**]

	Interfaces with [dotabase](http://github.com/mdiller/dotabase). Check out [dotabase.dillerm.io](http://dotabase.dillerm.io) if you want to see an old website I built that interfaces with dotabase."""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.session = session
		self.hero_stat_categories = read_json(settings.resource("json/hero_stats.json"))
		self.hero_aliases = {}
		self.item_aliases = {}
		self.leveled_hero_stats = [] # by level (0 is null, and 1-30 are filled in)
		self.hero_regex = ""
		self.item_regex_1 = ""
		self.item_regex_2 = ""
		self.patches_regex = ""
		self.build_helpers()
		self.vpkurl = "http://dotabase.dillerm.io/dota-vpk"
		drawdota.init_dota_info(self.get_hero_infos(), self.get_item_infos(), self.get_ability_infos(), self.vpkurl)
	
	@property
	def description(self):
		text = str(inspect.getdoc(self))
		text = re.sub("\{CURRENT_DOTA_PATCH_NUMBER\}", CURRENT_DOTA_PATCH_NUMBER, text)
		return text

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
		secondary_item_patterns = []
		for item in session.query(Item).filter(~Item.localized_name.contains("Recipe")):
			aliases = item.aliases.split("|")
			aliases.append(clean_input(item.localized_name))
			for alias in aliases:
				if alias not in self.item_aliases:
					self.item_aliases[alias] = item.id
					self.item_aliases[alias.replace(" ", "")] = item.id
			pattern = re.sub(r"[^a-z' ]", "", item.localized_name.lower())
			pattern = pattern.replace("'", "'?")
			if " " in pattern:
				secondary_item_patterns.extend(pattern.split(" "))
			item_patterns.append(pattern)
		self.item_regex_1 = f"(?:{'|'.join(item_patterns)})"
		item_patterns.extend(secondary_item_patterns)
		self.item_regex_2 = f"(?:{'|'.join(item_patterns)})"

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
		if isinstance(obj, LocaleWrapper):
			obj = obj.object
		if isinstance(obj, Hero):
			wikiurl = obj.localized_name
		elif isinstance(obj, Ability):
			wikiurl = f"{obj.hero.localized_name}#{obj.localized_name}"
		elif isinstance(obj, Item):
			wikiurl = obj.localized_name

		wikiurl = wikiurl.replace(" ", "_").replace("'", "%27")
		return f"http://dota2.gamepedia.com/{wikiurl}"
	
	# gets the patch a match took place in, else None
	def get_match_patch(self, match):
		query = session.query(Patch)
		timestamp = datetime.datetime.fromtimestamp(match['start_time'], tz=datetime.timezone.utc)
		query = query.filter(Patch.timestamp <= timestamp)
		query = query.order_by(desc(Patch.timestamp))
		query = query.limit(1)
		if query.count() > 0:
			return query.first().number
		else:
			return None

	def lookup_hero(self, hero, inter: disnake.CmdInter = None) -> Hero:
		if not hero:
			return None
		if isinstance(hero, str):
			hero = hero.strip()
		hero_id = self.lookup_hero_id(hero)
		if hero_id:
			result = session.query(Hero).filter(Hero.id == hero_id).first()
			if inter:
				result = LocaleWrapper.wrap(inter, result)
			return result
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

	def lookup_ability(self, text, full_check=True, inter: disnake.CmdInter = None) -> Ability:
		result = self._lookup_ability(text, full_check=full_check)
		if inter:
			result = LocaleWrapper.wrap(inter, result)
		return result

	def _lookup_ability(self, text, full_check=True) -> Ability:
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
						def filter_ulti(ability):
							for bad_behavior in [ "not_learnable", "hidden" ]:
								if bad_behavior in (ability.behavior or ""):
									return False
							return True
						abilities = list(filter(filter_ulti, abilities))
						ability_position = len(abilities)
					return abilities[ability_position - 1]
		return None

	def lookup_item(self, item, full_check=True, inter: disnake.CmdInter = None) -> Item:
		if not item:
			return None
		if isinstance(item, str):
			item = item.strip()
		item_id = self.lookup_item_id(item, full_check)
		if item_id:
			result = session.query(Item).filter(Item.id == item_id).first()
			if inter:
				result = LocaleWrapper.wrap(inter, result)
			return result
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
		if n == 1: 
			# assume user wants latest MAJOR patch
			for patch in query:
				if not re.search(r"[a-zA-Z]", patch.number):
					return patch
		if n > query.count() or n < 0:
			return None
		else:
			return query.all()[n - 1]

	def lookup_patch_and_bounds(self, patch_name):
		query = session.query(Patch).order_by(Patch.timestamp)
		start = None
		end = None

		for patch in query:
			if start is None:
				if patch.number == patch_name:
					start = patch.timestamp
			else:
				if re.sub(r"[a-z]", "", patch.number) != patch_name:
					end = patch.timestamp
					break
		if end is None:
			end = datetime.datetime.now()

		return (patch, start, end)


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
			return f"dotachatwheel:{message.id}"
		else:
			return None

	def get_chatwheel_sound(self, text, loose_fit=False):
		def simplify(t):
			t = re.sub(r"[?!',！？.-]", "", t.lower())
			return re.sub(r"[_，]", " ", t)
		text = simplify(text)
		if text == "":
			return None
		if text.startswith("dotachatwheel:"):
			text = text.replace("dotachatwheel:", "")
		if text.isdigit():
			query = session.query(ChatWheelMessage).filter_by(id=int(text)).filter(ChatWheelMessage.sound != None)
			if query.count() > 0:
				return query.first()

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

	async def play_response(self, response, clip_ctx: ClipContext):
		return await self.play_clip(f"dota:{response.fullname}", clip_ctx)

	# used for getting the right response for dota clips
	def get_response(self, responsename):
		response = session.query(Response).filter(Response.fullname == responsename).first()
		if response:
			return response
		# to support legacy clips that used name instead of fullname
		return session.query(Response).filter(Response.name == responsename).first()

	# Plays a random response from a query
	async def play_response_query(self, query, clip_ctx: ClipContext):
		return await self.play_response(query.order_by(func.random()).first(), clip_ctx)

	@Audio.play.sub_command(name="dota")
	async def play_dota(self, inter: disnake.CmdInter, text: str = None, hero: Hero = None, criteria: commands.option_enum(CRITERIA_ALIASES) = None):
		"""Plays a dota response. Try '/clips dota' for a similar command that returns a list

		Parameters
		----------
		text: Some text contained within the response you're searching for
		hero: A dota hero that says this clip
		criteria: An action or situation that causes the hero to say this clip
		"""
		query = await self.smart_dota_query(text, hero=hero, criteria=criteria)

		if query is None:
			await inter.send("No responses found! 😱")
		else:
			clip = await self.play_response_query(query, inter)
			await self.print_clip(inter, clip)
	
	@Audio.clips.sub_command(name="dota")
	async def clips_dota(self, inter: disnake.CmdInter, text: str = None, hero: Hero = None, criteria: commands.option_enum(CRITERIA_ALIASES) = None, page: commands.Range[int, 1, 10] = 1):
		"""Searches for dota responses

		Parameters
		----------
		text: Some text contained within the response you're searching for
		hero: A dota hero that says this clip
		criteria: An action or situation that causes the hero to say this clip
		page: Which page of clips to view
		"""
		query = await self.smart_dota_query(text, hero=hero, criteria=criteria)

		clipids = []
		cliptext = []
		response_limit = 200
		if query is not None:
			query = query.limit(response_limit)
			for response in query.all():
				clipids.append(f"dota:{response.fullname}")
				text = response.text
				sizelimit = 45
				if len(text) > sizelimit:
					text = text[:sizelimit - 3] + "..."
				cliptext.append(text)
		audio_cog = self.bot.get_cog("Audio")
		await audio_cog.clips_pager(inter, "Dota Hero Responses", clipids, cliptext, page=page, more_pages=len(clipids) == response_limit)

	async def smart_dota_query(self, keyphrase, hero: Hero = None, criteria: str = None, exact = False):
		if keyphrase is None:
			keyphrase = ""
		keyphrase = keyphrase.lower()
		keyphrase = " ".join(keyphrase.split(" "))

		basequery = session.query(Response)

		if hero:
			basequery = basequery.filter(Response.hero_id == hero.id)
		if criteria:
			basequery = basequery.filter(or_(Response.criteria.like(criteria + "%"), Response.criteria.like("%|" + criteria + "%")))


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

	async def get_laugh_response(self, hero=None):
		query = session.query(Response)
		hero = self.lookup_hero(hero)
		if hero is not None:
			query = query.filter(Response.hero_id == hero.id)
		query = query.filter(Response.criteria.like(f"%|HeroChatWheel%"))
		query = query.filter(Response.criteria.like(f"%IsEmoteLaugh%"))
		query = query.order_by(func.random())

		response = query.first()
		if response is None:
			query = session.query(Response)
			query = query.filter(Response.hero_id == hero.id)
			query = query.filter(Response.criteria.like(f"%IsEmoteLaugh%"))
			response = query.first()
		return response

	@Audio.play.sub_command(name="chatwheel")
	async def play_chatwheel(self, inter: disnake.CmdInter, text: str):
		"""Plays the given chat wheel sound. Try '/clips chatwheel' to get a list of clips.

		Parameters
		----------
		text: The text shown when the chatwheel is played
		"""
		message = self.get_chatwheel_sound(text, True)
		if message is None:
			raise UserError(f"Couldn't find chat wheel sound '{text}'")

		await self.play_clip(f"dotachatwheel:{message.id}", inter, print=True)
	
	@Audio.clips.sub_command(name="chatwheel")
	async def clips_chatwheel(self, inter: disnake.CmdInter, text: str, page: commands.Range[int, 1, 50] = 1):
		"""Shows a list of chatwheel lines
		
		Parameters
		----------
		text: Part of the text shown when the chatwheel is played. Say "all" to get all chatwheel messages.
		page: Which page of clips to view
		"""
		query = session.query(ChatWheelMessage).filter(ChatWheelMessage.sound.like("/%"))
		if text != "all":
			query = query.filter(ChatWheelMessage.message.ilike(f"%{text}%"))
		clipids = []
		cliptext = []
		for message in query.all():
			clipids.append(f"dotachatwheel:{message.id}")
			text = message.message
			sizelimit = 45
			if len(text) > sizelimit:
				text = text[:sizelimit - 3] + "..."
			cliptext.append(text)
		audio_cog = self.bot.get_cog("Audio")
		await audio_cog.clips_pager(inter, "Dota Chatwheel Lines", clipids, cliptext, page=page)

	@commands.slash_command()
	async def hero(self, inter: disnake.CmdInter, hero: Hero):
		"""Gets information about a specific hero
		
		Parameters
		----------
		hero: The name or id of the hero
		"""
		await inter.response.defer()

		description = ""
		def add_attr(name, base_func, gain_func):
			global description
			result = f"{base_func(hero)} + {gain_func(hero)}"
			if hero.attr_primary == name:
				result = f"**{result}**"
			icon = self.get_emoji(f"attr_{name}")
			return f"{icon} {result}\n"

		description += hero.hype

		embed = disnake.Embed(description=description)

		if hero.color:
			embed.color = disnake.Color(int(hero.color[1:], 16))

		wikiurl = self.get_wiki_url(hero)

		embed.set_author(name=hero.localized_name, icon_url=f"{self.vpkurl}{hero.icon}", url=wikiurl)
		embed.set_thumbnail(url=f"{self.vpkurl}{hero.portrait}")

		base_damage = {
			"strength": hero.attr_strength_base,
			"agility": hero.attr_agility_base,
			"intelligence": hero.attr_intelligence_base,
			"universal": (hero.attr_strength_base + hero.attr_agility_base + hero.attr_intelligence_base) * 0.6
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
		
		stats_value = add_attr("strength", lambda h: h.attr_strength_base, lambda h: h.attr_strength_gain)
		stats_value += add_attr("agility", lambda h: h.attr_agility_base, lambda h: h.attr_agility_gain)
		stats_value += add_attr("intelligence", lambda h: h.attr_intelligence_base, lambda h: h.attr_intelligence_gain)
		embed.add_field(name="Stats", value=stats_value)

		if hero.real_name != '':
			embed.add_field(name="Real Name", value=hero.real_name)

		roles = hero.roles.split("|")
		embed.add_field(name=f"Role{'s' if len(roles) > 1 else ''}", value=', '.join(roles))

		await inter.send(embed=embed)

		query = session.query(Response).filter(Response.hero_id == hero.id).filter(or_(Response.criteria.like("Spawn %"), Response.criteria.like("Spawn%")))
		if query.count() > 0:
			try:
				await self.play_response_query(query, inter)
			except AudioPlayerNotFoundError:
				pass

	@commands.slash_command()
	async def talents(self, inter: disnake.CmdInter, hero: Hero):
		"""Gets the talents of a specific hero
		
		Parameters
		----------
		hero: The name of the hero
		"""
		await inter.response.defer()
		
		# talents = list(map(lambda t: LocaleWrapper.wrap(inter, t.ability).localized_name, hero.talents))
		image = await drawdota.draw_hero_talents(hero)
		image = disnake.File(image, f"{hero.name}_talents.png")

		await inter.send(file=image)


	@commands.slash_command()
	async def ability(self, inter: disnake.CmdInter, ability: Ability):
		"""Gets information about a specific hero ability

		Parameters
		----------
		ability: The name of the ability, or a hero name and the ability slot
		"""
		await inter.response.defer()

		def format_values(values):
			if values is None:
				return None
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
		scepter_attributes = []
		shard_attributes = []
		for attribute in ability_special:
			header = attribute.get("header")
			if not header:
				continue
			header = format_pascal_case(header)
			is_scepter_upgrade = attribute.get("scepter_upgrade")
			is_shard_upgrade = attribute.get("shard_upgrade")

			value = attribute.get("value")
			footer = attribute.get("footer")
			if value is None:
				if attribute.get("scepter_value"):
					is_scepter_upgrade = True
					value = attribute.get("scepter_value")
				elif attribute.get("shard_value"):
					is_shard_upgrade = True
					value = attribute.get("shard_value")
				else:
					continue

			text = f"**{header}** {format_values(value)}"
			if footer:
				text += f" {footer}"

			if is_scepter_upgrade and not ability.scepter_grants:
				scepter_attributes.append(text)
			elif is_shard_upgrade and not ability.shard_grants:
				shard_attributes.append(text)
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
				for attribute in scepter_attributes:
					description += f"\n{attribute}"

		# aghs shard
		if ability.shard_description:
			if ability.shard_grants:
				description += f"\n\n{self.get_emoji('aghanims_shard')} **Granted by Aghanim's Shard**"
			else:
				description += f"\n\n{self.get_emoji('aghanims_shard')} __**Upgradable by Aghanim's Shard**__\n"
				description += f"*{ability.shard_description}*\n"
				for attribute in shard_attributes:
					description += f"\n{attribute}"

		embed = disnake.Embed(description=description)

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

		await inter.send(embed=embed)

	@commands.slash_command()
	async def item(self, inter: disnake.CmdInter, item: Item):
		"""Gets information about a specific dota 2 item

		Parameters
		----------
		item: The name of the dota 2 item to get
		"""
		await inter.response.defer()

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

		embed = disnake.Embed(description=description)

		color = drawdota.get_item_color(item)
		if color is not None:
			embed.color = disnake.Color(int(color[1:], 16))


		embed.title = item.localized_name
		embed.url = self.get_wiki_url(item)

		embed.set_thumbnail(url=f"{self.vpkurl}{item.icon}")

		if item.lore and item.lore != "":
			embed.set_footer(text=item.lore)

		await inter.send(embed=embed)

	@commands.slash_command()
	async def emoticon(self, inter: disnake.CmdInter):
		"""Commands for dota 2 emotes"""
		await inter.response.defer()

	@emoticon.sub_command(name="show")
	async def emoticon_show(self, inter: disnake.CmdInter, name):
		"""Gets the gif of a dota emoticon

		Parameters
		----------
		name: The in-game name of the emoticon
		"""
		emoticon = session.query(Emoticon).filter(Emoticon.name == name).first()

		if not emoticon:
			raise UserError(f"Couldn't find an emoticon with the name '{name}'")

		url = self.vpkurl + emoticon.url

		filetype = "gif" if emoticon.frames > 1 else "png"
		image = disnake.File(await drawdota.create_dota_emoticon(emoticon, url), f"{name}.{filetype}")

		await inter.send(file=image)

	@emoticon.sub_command(name="add")
	async def emoticon_add(self, inter: disnake.CmdInter, name):
		"""Adds a dota emoticon as an animated emoji to this server

		Parameters
		----------
		name: The in-game name of the emoticon
		"""
		emoticon = session.query(Emoticon).filter(Emoticon.name == name).first()

		if not emoticon:
			raise UserError(f"Couldn't find an emoticon with the name '{name}'")

		url = self.vpkurl + emoticon.url
		image = await drawdota.create_dota_emoticon(emoticon, url)
		with open(image, 'rb') as f:
			image = f.read()

		if not inter.guild:
			raise UserError("You have to be in a server to use this command")

		if not inter.guild.me.guild_permissions.manage_emojis:
			raise UserError("An admin needs to give me the 'Manage Emojis' permission before I can do that")

		await inter.guild.create_custom_emoji(name=name, image=image, reason=f"Dota emoji created for {inter.author.name}")

		await inter.send("✅ done!")

	@commands.slash_command()
	async def lore(self, inter: disnake.CmdInter, name: str):
		"""Gets the lore of a hero, ability, or item

		Parameters
		----------
		name: The name of a hero, ability, or item. Leave blank to get random lore!
		"""
		await inter.response.defer()
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

		item = self.lookup_item(name, False, inter=inter)
		if item:
			found = True
			lore_info = {
				"name": item.localized_name,
				"icon": item.icon,
				"lore": item.lore,
				"object": item
			}

		if not found:
			ability = self.lookup_ability(name, False, inter=inter)
			if ability:
				found = True
				lore_info = {
					"name": ability.localized_name,
					"icon": ability.icon,
					"lore": ability.lore,
					"object": ability
				}

		if not found:
			hero = self.lookup_hero(name, inter=inter)
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
		embed = disnake.Embed(description=lore_text)

		embed.title = lore_info["name"]
		embed.url = self.get_wiki_url(lore_info["object"])

		if lore_info["icon"]:
			embed.set_thumbnail(url=f"{self.vpkurl}{lore_info['icon']}")

		await inter.send(embed=embed)

	@commands.slash_command()
	async def aghanim(self, inter: disnake.CmdInter, name: str, type: commands.option_enum(["Both", "Scepter", "Shard"]) = "Both"):
		"""Gets the aghs upgrade for the given hero or ability

		Parameters
		----------
		name: The name of the hero or ability to get aghanim info for
		type: The type of aghanim information you're looking for
		"""
		await inter.response.defer()
		only_do_scepter = type == "Scepter"
		only_do_shard = type == "Shard"

		abilities = []
		hero = self.lookup_hero(name, inter=inter)
		if hero:
			for ability in hero.abilities:
				if (ability.shard_upgrades or ability.shard_grants) and not only_do_scepter:
					abilities.append(ability)
				elif (ability.scepter_upgrades or ability.scepter_grants) and not only_do_shard:
					abilities.append(ability)

			if len(abilities) == 0:
				raise UserError(f"Couldn't find an aghs upgrade for {hero.localized_name}. Either they don't have one or I just can't find it.")
		else:
			ability = self.lookup_ability(name, True, inter)
			if not ability:
				raise UserError("Couldn't find a hero or ability by that name")
			abilities = [ ability ]

		item_shard = self.lookup_item("aghanim's shard", inter=inter)
		item_scepter = self.lookup_item("aghanim's scepter", inter=inter)
		upgrade_types = [ "scepter", "shard" ]
		if only_do_scepter:
			upgrade_types = [ "scepter" ]
		elif only_do_shard:
			upgrade_types = [ "shard" ]

		for upgrade_type in upgrade_types:
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
						if not (header and attribute.get("scepter_upgrade")):
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
				embed = disnake.Embed(description=description)
				title = f"{aghs_item.localized_name} ({ability.localized_name})"
				embed.set_author(name=title, icon_url=icon_url)
				embed.set_thumbnail(url=f"{self.vpkurl}{ability.icon}")
				await inter.send(embed=embed)

	@commands.slash_command()
	async def recipe(self, inter: disnake.CmdInter, item: Item):
		"""Shows the recipes involving this item
		
		Parameters
		----------
		item: The name of the dota 2 item to get
		"""
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


		embed = disnake.Embed()

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
			embed.color = disnake.Color(int(color[1:], 16))

		image = disnake.File(await drawdota.draw_itemrecipe(item, components, products), "recipe.png")
		embed.set_image(url=f"attachment://{image.filename}")

		await inter.send(embed=embed, file=image)


	@commands.slash_command()
	async def fuseheroes(self, inter: disnake.CmdInter, hero1: Hero, hero2: Hero):
		"""Visually fuse together two heroes

		Parameters
		----------
		hero1: The first of the two heroes to fuse
		hero2: The second of the two heroes to fuse
		"""
		await inter.response.defer()

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


		embed = disnake.Embed()

		embed.title = hero_name

		emoji1 = self.get_emoji(f"dota_hero_{hero1.name}")
		emoji2 = self.get_emoji(f"dota_hero_{hero2.name}")

		embed.description = f"{emoji1} + {emoji2}"

		color1 = imagetools.Color(hero1.color)
		color2 = imagetools.Color(hero2.color)
		color = color1.blend(color2)
		embed.color = disnake.Color(color.integer)

		image = disnake.File(await drawdota.fuse_hero_images(hero1, hero2), "hero.png")
		embed.set_thumbnail(url=f"attachment://{image.filename}")

		await inter.send(embed=embed, file=image)


	@commands.slash_command()
	async def courage(self, inter: disnake.CmdInter, hero: Hero = None):
		"""Generates a challenge build with a random hero and items

		Parameters
		----------
		hero: The hero to use. Leave this blank to random a hero
		"""

		all_boots = query_filter_list(session.query(Item), Item.recipe, "item_boots").all()

		random.seed(datetime.datetime.now())
		items = session.query(Item) \
			.filter(~Item.localized_name.contains("Recipe")) \
			.filter(~Item.localized_name.contains("Boots")) \
			.filter(Item.recipe != None) \
			.filter(Item.icon != None) \
			.filter(Item.cost > 2000) \
			.order_by(func.random()) \
			.limit(5) \
			.all()
		items.append(random.choice(all_boots))
		random.shuffle(items)

		item_ids = []
		for item in items:
			item_ids.append(item.id)
		if hero:
			hero_id = hero.id
		else:
			hero_id = session.query(Hero).order_by(func.random()).first().id

		logger.info(item_ids)

		image = disnake.File(await drawdota.draw_courage(hero_id, item_ids), "courage.png")
		await inter.send(file=image)


	@commands.slash_command()
	async def neutralitems(self, inter: disnake.CmdInter, tier: commands.Range[int, 0, 5] = 0):
		"""Displays neutral item information
		
		Parameters
		----------
		tier: The neutral item tier to show
		"""
		await inter.response.defer()
		if tier == 0:
			tier = None

		embed = disnake.Embed()

		title = "Neutral Items"
		if tier is not None:
			title = f"Tier {tier} Neutral Items"
		embed.title = title
		embed.url = "https://dota2.gamepedia.com/Neutral_Items"

		all_neutral_items = session.query(Item).filter(Item.neutral_tier != None).filter(Item.recipe == None).order_by(Item.localized_name).all()
		image = disnake.File(await drawdota.draw_neutralitems(tier, all_neutral_items), "neutralitems.png")
		embed.set_image(url=f"attachment://{image.filename}")
		if tier is not None:
			tier_color = drawdota.neutral_tier_colors[str(tier)]
			embed.color = disnake.Color(int(tier_color[1:], 16))

		if tier is None:
			embed.set_footer(text="Also try: /neutralitems tier 4")
		await inter.send(embed=embed, file=image)

	@commands.slash_command()
	async def herostats(self, inter: disnake.CmdInter, hero: Hero, level: commands.Range[int, 1, 30] = 1):
		"""Gets the stats for a hero at the specified level

		Parameters
		----------
		hero: The hero to use. Leave this blank to random a hero
		level: What level view the stats of this hero at
		"""
		await inter.response.defer()
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

		embed = disnake.Embed(description=description)

		title = f"Level {level} {hero.localized_name}"
		embed.set_author(name=title, icon_url=f"{self.vpkurl}{hero.icon}")
		embed.set_thumbnail(url=f"{self.vpkurl}{hero.portrait}")
		if hero.color:
			embed.color = disnake.Color(int(hero.color[1:], 16))
		embed.set_footer(text="The stats shown above do not account for talents, passives, or items")

		await inter.send(embed=embed)

	@commands.slash_command()
	async def herotable(self, inter: disnake.CmdInter, stat: HERO_STAT_ENUM, level: commands.Range[int, 1, 30] = 1, hero_count: commands.Range[int, 2, 40] = 20, reverse: bool = False):
		"""Displays a table of dota heroes sorted by a stat

		Parameters
		----------
		stat: The stat to sort the table by
		level: What level the stats of the heroes should be calculated at
		hero_count: The number of hero rows to show
		reverse: Whether or not the sorting should be reversed
		"""
		await inter.response.defer()
		embed = disnake.Embed()

		image = disnake.File(await drawdota.draw_herostatstable(stat, level, hero_count, reverse, self.hero_stat_categories, self.leveled_hero_stats), "herotable.png")
		embed.set_image(url=f"attachment://{image.filename}")
		embed.set_footer(text="The stats shown above do not account for talents, passives, or items")

		await inter.send(embed=embed, file=image)

	@commands.slash_command()
	async def abilities(self, inter: disnake.CmdInter, hero: Hero):
		"""Shows all of the abilities/spells for that hero

		Parameters
		----------
		hero: The hero who's abilities to show
		"""
		await inter.response.defer()
		abilities = []
		for ability in list(filter(lambda a: a.slot is not None, hero.abilities)):
			if not hero.id == 74: # invoker
				if "hidden" in (ability.behavior or "") and not (ability.shard_grants or ability.scepter_grants):
					continue
			abilities.append(ability)

		embed = disnake.Embed()

		embed.title = hero.localized_name
		embed.url = self.get_wiki_url(hero)

		image = disnake.File(await drawdota.draw_heroabilities(abilities), "abilities.png")
		embed.set_image(url=f"attachment://{image.filename}")

		embed.color = disnake.Color(int(hero.color[1:], 16))

		await inter.send(embed=embed, file=image)

	# disabling this as a command for now because valve broke this blog feed. (was rss feed before)
	async def blog(self,ctx):
		""" Pulls the newest blog post for Dota 2"""
		# await ctx.send("Sorry, Valve broke this for now.")
		# return # return cuz valve broke it
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
					logger.info(f"couldn't find channel {guildinfo.dotablogchannel} when announcing dota blog")

		#find users
		userinfos = botdata.userinfo_list()
		for userinfo in userinfos:
			if userinfo.dmdotablog:
				user = self.bot.get_user(userinfo.discord)
				if user is not None:
					messageables.append(user)
				else:
					logger.info(f"couldn't find user {userinfo.discord} when announcing dota blog")

		#bundle tasks and execute
		tasks = []
		for messageable in messageables:
			tasks.append(messageable.send(embed=embed))

		bundler = AsyncBundler(tasks)
		await bundler.wait()


def setup(bot):
	bot.add_cog(Dotabase(bot))
