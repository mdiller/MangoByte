import chunk
import datetime
import math
import re
from collections import OrderedDict
from functools import lru_cache
from enum import Enum


import disnake
from disnake.ext import commands
from tinydb import Query
from utils.tools.globals import botdata, httpgetter, logger, settings
from utils.tools.helpers import *


@lru_cache(maxsize=None)
def get_cache_hero_pattern(dotabase, prefix):
	pattern = f"{prefix}{dotabase.hero_regex}"
	pattern = f"\\b(?:{pattern})\\b"
	pattern = re.compile(pattern, re.IGNORECASE)
	return pattern

@lru_cache(maxsize=None)
def get_item_pattern(dotabase, level=1):
	regex_levels = [
		dotabase.item_regex_1,
		dotabase.item_regex_2
	]
	pattern = f"\\b{regex_levels[level - 1]}\\b"
	pattern = re.compile(pattern, re.IGNORECASE)
	return pattern

hero_stats_patterns = OrderedDict()
def get_cache_hero_stats_patterns(dotabase):
	global hero_stats_patterns
	if not hero_stats_patterns:
		patterns = OrderedDict()
		for category in dotabase.hero_stat_categories:
			for stat in category["stats"]:
				pattern = stat["name"]
				if "regex" in stat:
					pattern = stat["regex"]
				patterns[stat["stat"]] = pattern
		patterns = OrderedDict(reversed(list(patterns.items())))
		all_pattern = list(map(lambda p: f"(?:{p})", patterns.values()))
		all_pattern = f"(?:{'|'.join(all_pattern)})"
		patterns["all"] = all_pattern
		for stat in patterns:
			patterns[stat] = re.compile(patterns[stat], re.IGNORECASE)
		hero_stats_patterns = patterns
	return hero_stats_patterns

game_mode_arg_options = {}
def get_cache_game_mode_arg_options():
	global game_mode_arg_options
	if not game_mode_arg_options:
		options = []
		dota_strings = read_json(settings.resource("json/dota_game_strings.json"))
		for key in dota_strings:
			prefix = "game_mode_"
			if prefix not in key:
				continue
			mode_id = int(key.replace(prefix, ""))
			name = dota_strings[key]
			pattern = name.lower()
			options.append(ArgOption(mode_id, name, pattern))
		game_mode_arg_options = options
	return game_mode_arg_options

region_arg_options = {}
def get_cache_region_arg_options():
	global region_arg_options
	if not region_arg_options:
		options = []
		dota_strings = read_json(settings.resource("json/region_data.json"))
		for key in dota_strings:
			region_id = int(key)
			name = dota_strings[key]["name"]
			pattern = name.lower()
			options.append(ArgOption(region_id, name, pattern))
		region_arg_options = options
	return region_arg_options

def clean_input(t):
	return re.sub(r'[^a-z1-9\s]', r'', str(t).lower())

class SteamNotLinkedError(UserError):
	def __init__(self, user=None):
		self.is_author = user is None
		self.user = user
		if not self.is_author:
			super().__init__(f"{user.name} doesn't have a steam account linked to mangobyte. They should try `/userconfig steam show` to see how to link their steam account to mangobyte.")
		else:
			super().__init__("Ya haven't told me what yer steam account is.\nTry doin' `/userconfig steam show` to see how to link a steam account to mangobyte.")

class NoMatchHistoryError(UserError):
	def __init__(self, steam_id):
		super().__init__(f"")
		self.embed = disnake.Embed(description=f"It looks like you either haven't played dota on this account, or the matches you've played are hidden. If you've played matches on this account, you should try enabling the **Expose Public Match Data** option in dota (see image below). Once you've done that, go to [your opendota profile](http://www.opendota.com/players/{steam_id}) and click the button under your name that says **REFRESH**")
		self.file = disnake.File(settings.resource("images/expose_match_data.png"), "tip.png")
		self.embed.set_image(url=f"attachment://{self.file.filename}")

class CustomBadArgument(commands.BadArgument):
	def __init__(self, user_error):
		super().__init__()
		self.user_error = user_error


class InputParser():
	def __init__(self, text):
		self.text = text

	def trim(self):
		self.text = self.text.strip()
		self.text = re.sub(r"\s+", " ", self.text)

	def take_regex(self, pattern, add_word_boundary=True):
		if isinstance(pattern, str):
			if add_word_boundary:
				pattern = f"\\b(?:{pattern})(?:\\b|(?=( |$)))"
			pattern = re.compile(pattern, re.IGNORECASE)
		match = re.search(pattern, self.text)
		if match is None:
			return None
		self.text = re.sub(pattern, "", self.text, count=1)
		self.trim()
		return match.group(0)


opendota_html_errors = {
	404: "Dats not a valid query. Take a look at the OpenDota API Documentation: https://docs.opendota.com",
	521: "[http error 521] Looks like the OpenDota API is down or somethin, so ya gotta wait a sec",
	502: "[http error 502] Looks like there was an issue with the OpenDota API. Try again in a bit",
	"default": "OpenDota said we did things wrong 😢. http status code: {}"
}


class DotaPlayer():
	def __init__(self, steam_id, mention=None, is_author=False):
		self.steam_id = steam_id
		self.mention = mention
		self.is_author = is_author

	@classmethod
	async def from_author(cls, inter):
		return await cls.convert(inter, None)

	@commands.converter_method
	async def convert(cls, inter: disnake.CmdInter, player: str):
		await safe_defer(inter)
		is_author = player is None or player == ""
		if is_author:
			player = inter.author

		try:
			player = int(player)
		except (ValueError, TypeError):
			pass # This either this is a discord user or an invalid argument

		if isinstance(player, int):
			if player > 76561197960265728:
				player -= 76561197960265728
			# Don't have to rate limit here because this will be first query ran
			player_info = await httpgetter.get(f"https://api.opendota.com/api/players/{player}", cache=False, errors=opendota_html_errors)

			if player_info.get("profile") is None:
				raise CustomBadArgument(NoMatchHistoryError(player))
			return cls(player, f"[{player_info['profile']['personaname'] or 'Anonymous'}](https://www.opendota.com/players/{player})", is_author)

		if isinstance(player, disnake.abc.User):
			player = player.mention

		# assume its a user at this point
		match = re.match(r"<@!?(\d+)>", player)
		if not match:
			raise CustomBadArgument(UserError("Ya gotta @mention a user who has been linked to a steam id, or just give me their steam id"))
		user_id = match.group(1)

		userinfo = botdata.userinfo(int(user_id))
		if userinfo.steam is None:
			raise CustomBadArgument(SteamNotLinkedError())
		return cls(userinfo.steam, f"<@!{user_id}>", is_author)

# the thing we should wrap values with to highlight them in localized matchfilters
LOCALIZE_HIGHLIGHT_WRAPPER = "**"

class ArgOption():
	def __init__(self, value, localized, regex):
		self.value = value
		self.localized = localized
		self.regex = regex

class QueryArg():
	def __init__(self, name, args=None, post_filter=None, check_filter=None, parse_levels=1, localization_context=None, localization_index=0):
		self.name = name
		self.args: typing.List[ArgOption]
		self.args = args or []
		self.post_filter = post_filter
		self.check_filter = check_filter
		self.value = None
		self.parse_levels = parse_levels
		self.localization_context = localization_context
		self.localization_index = localization_index

	async def parse(self, text, level=1):
		for arg in self.args:
			key = arg.regex
			match = re.match(key, text)
			if match:
				value = arg.value
				if callable(value):
					value = value(match)
				self.value = value

	def has_value(self):
		return self.value is not None

	def regex(self):
		return "|".join(map(lambda k: f"(?:{k.regex})", self.args))

	def to_query_arg(self):
		return f"{self.name}={self.value}"

	def check_post_filter(self, p):
		if self.has_value():
			if self.post_filter is not None:
				return self.post_filter.func(p)
		return True
	
	def localize(self):
		if self.has_value():
			for arg in self.args:
				if arg.value == self.value or (callable(arg.value) and len(self.args) == 1):
					result = arg.localized
					if result is None:
						return None
					result = result.format(value=self.value)
					if LOCALIZE_HIGHLIGHT_WRAPPER not in result:
						result = f"{LOCALIZE_HIGHLIGHT_WRAPPER}{result}{LOCALIZE_HIGHLIGHT_WRAPPER}"
					return result
		return None


# added manually
class SimpleQueryArg(QueryArg):
	def __init__(self, name, value):
		super().__init__(name)
		self.value = value



# a span of time to look in
class TimeSpanArg(QueryArg):
	def __init__(self, inter, **kwargs):
		kwargs["post_filter"] = PostFilter("start_time", self.post_filter_checker)
		super().__init__("date", **kwargs)
		self.dotabase = inter.bot.get_cog("Dotabase")
		self.localized_value = None
		self.min = None
		self.max = None
		self.value = None

	async def parse(self, text):
		match = re.match(self.regex(), text)
		k = match.group("kind")
		c = match.group("count")

		if match.group("kind"):
			chunk_count = float(match.group("count") or "1")
			if chunk_count == 0:
				self.value = 0
				return
			chunk_kind = match.group("kind")
			self.localization_kind = chunk_kind
			if chunk_kind == "patch":
				patch = self.dotabase.lookup_nth_patch(round(chunk_count))
				self.min = patch.timestamp
				self.localized_value = "since patch " + f"{LOCALIZE_HIGHLIGHT_WRAPPER}{patch.number}{LOCALIZE_HIGHLIGHT_WRAPPER}"
			else:
				chunk_kind_value = {
					"hour": 1 / 24,
					"today": 16 / 24,
					"day": 1,
					"week": 7,
					"month": 30,
					"year": 365
				}[chunk_kind]
				numdays = chunk_count * chunk_kind_value
				min_datetime = datetime.datetime.now() - datetime.timedelta(days=numdays)
				self.min = min_datetime
				# localize
				def pretty_number(num):
					num = str(num)
					num = re.sub(r".0$", "", num)
					return num
				self.localized_value = f"in the last {LOCALIZE_HIGHLIGHT_WRAPPER}"
				localized_chunk = chunk_kind
				if chunk_count != 1:
					self.localized_value += f"{pretty_number(chunk_count)} "
					localized_chunk += "s"
				if localized_chunk == "today":
					localized_chunk = f"{pretty_number(chunk_kind_value * 24)} hours"
				self.localized_value += localized_chunk
				self.localized_value += LOCALIZE_HIGHLIGHT_WRAPPER
		else:
			patch_name = match.group("patch")
			patch, self.min, self.max = self.dotabase.lookup_patch_and_bounds(patch_name)
			self.localized_value = f"{LOCALIZE_HIGHLIGHT_WRAPPER}{patch.number}{LOCALIZE_HIGHLIGHT_WRAPPER}"
			if match.group("since") is not None:
				self.max = None
				self.localized_value = "since patch " + self.localized_value
			else:
				self.localized_value = "during patch " + self.localized_value


	def post_filter_checker(self, p):
		match_time = datetime.datetime.fromtimestamp(p["start_time"])
		if self.min:
			if match_time < self.min:
				return False
		if self.max:
			if match_time > self.max:
				return False
		return True

	@property
	def value(self):
		if self.min is None:
			return None
		diff = datetime.datetime.now() - self.min
		return math.ceil(diff.days + 2) # doesn't matter much because this is just for the request, not for the post filter

	@value.setter
	def value(self, v):
		pass

	def regex(self):
		pattern = "(?:(?:in|over|during) )?"
		pattern += f"((?P<since>since )?(?:patch )?(?P<patch>{self.dotabase.patches_regex})|(?:the )?(?:(?:this|last|past) )?(?:(?P<count>\\d{{1,5}}\\.?\\d{{0,5}}?) )?(?P<kind>(?:to)?day|week|month|year|patch|hour)e?s?)"
		pattern = f"\\b{pattern}\\b"
		pattern = re.compile(pattern, re.IGNORECASE)
		return pattern
	
	def localize(self):
		return self.localized_value

all_item_slots = [ "item_0", "item_1", "item_2", "item_3", "item_4", "item_5", "item_neutral" ]
class ItemArg(QueryArg):
	def __init__(self, inter, name, **kwargs):
		kwargs["post_filter"] = PostFilter(all_item_slots, self.post_filter_checker)
		kwargs["parse_levels"] = 2
		super().__init__(name, **kwargs)
		self.dotabase = inter.bot.get_cog("Dotabase")
		self.item = None

	def post_filter_checker(self, p):
		for slot in all_item_slots:
			if p[slot] == self.value:
				return True
		return False

	def regex(self, level=1):
		return get_item_pattern(self.dotabase, level)

	async def parse(self, text, level=1):
		self.item = self.dotabase.lookup_item(text)
		self.value = self.item.id

	def localize(self):
		result = self.item.localized_name
		result = f"{LOCALIZE_HIGHLIGHT_WRAPPER}{result}{LOCALIZE_HIGHLIGHT_WRAPPER}"
		return result


class HeroArg(QueryArg):
	def __init__(self, inter, name, prefix, localization_template = None, **kwargs):
		super().__init__(name, **kwargs)
		self.prefix = prefix
		self.dotabase = inter.bot.get_cog("Dotabase")
		self.localization_template = localization_template
		self.hero = None

	def regex(self):
		return get_cache_hero_pattern(self.dotabase, self.prefix)

	async def parse(self, text):
		text = re.sub(self.prefix, "", text, flags=re.IGNORECASE)
		self.hero = self.dotabase.lookup_hero(text)
		self.value = self.hero.id
	
	def localize(self):
		result = self.hero.localized_name
		result = f"{LOCALIZE_HIGHLIGHT_WRAPPER}{result}{LOCALIZE_HIGHLIGHT_WRAPPER}"
		if self.localization_template:
			result = self.localization_template.format(result)
		return result

class PlayerArg(QueryArg):
	player: DotaPlayer
	def __init__(self, inter, name, prefix, **kwargs):
		super().__init__(name, **kwargs)
		self.inter = inter
		self.prefix = prefix
		self.player = None

	def regex(self):
		pattern = "(<@[!&]?[0-9]+>|\d{5,19})"
		if self.prefix == "":
			return re.compile(pattern)
		return f"{self.prefix}{pattern}"

	def set_player(self, player):
		self.player = player
		self.value = player.steam_id

	def localize(self):
		if self.player is None:
			return "you"
		return self.prefix + self.player.mention

	async def parse(self, text):
		text = re.sub(self.prefix, "", text, flags=re.IGNORECASE)
		self.set_player(await DotaPlayer.convert(self.inter, text))

# a filter to be applied to the match after retrieval, to supplement the actual query where needed
class PostFilter():
	def __init__(self, key, func):
		self.key = key
		self.func = func

# a filter that can fully replace the query, for use on already-queried data
# func is match, value (THIS ISNT FINSHED)
class CheckFilter():
	def __init__(self, keys, func):
		if isinstance(keys, str):
			keys = [keys]
		self.keys = keys
		self.func = func


class LocalizationContext(str, Enum):
	PreMatch = 'prematch'
	PostMatch = 'postmatch'
	WhoWith = 'whowith'
	PlayerLocation = 'playerloc'

# matches arg may be included to give the localizer more info
def localize_matchfilter(matchfilter, matches = None):
	args: typing.List[QueryArg]
	args = matchfilter.args
	def get_single_val(key):
		for arg in args:
			if arg.name == key:
				if arg.has_value():
					return arg.localize()
				else:
					return None
		return None
	def get_context(context):
		c_args = []
		for arg in args:
			if arg.has_value() and arg.localization_context == context:
				destination_index = len(c_args)
				for index in range(len(c_args)):
					if c_args[index].localization_index > arg.localization_index:
						destination_index = index
						break
				if destination_index == len(c_args):
					c_args.append(arg)
				else:
					c_args.insert(destination_index, arg)
		if not c_args:
			return None
		c_args = list(filter(lambda a: a is not None, map(lambda a: a.localize(), c_args)))
		return " ".join(c_args)
	
	# x matches/match played/won by _ as x, with/without _ where _
	phrases = []
	matchword = "matches"
	limit_count = matchfilter.get_arg("limit")
	if (matches is not None) and limit_count and len(matches) < limit_count:
		limit_count = None # if the limit wasn't used, then don't mention it
	if limit_count:
		phrases.append("The last")
		if limit_count == 1:
			matchword = "match"
		else:
			phrases.append(f"{LOCALIZE_HIGHLIGHT_WRAPPER}{limit_count}{LOCALIZE_HIGHLIGHT_WRAPPER}")
	else:
		phrases.append("All")
	
	# what kind of matches
	phrases.append(get_context(LocalizationContext.PreMatch))

	# "match" or "matches"
	phrases.append(matchword)

	# who played the matches
	phrases.append((get_single_val("win") or "played"))
	phrases.append("by " + get_single_val("_player"))
	# TODO: do custom stuff here for heroes & items etc
	hero = get_single_val("hero_id")
	item = get_single_val("_item")
	location = get_context(LocalizationContext.PlayerLocation) # lane & maybe position in future
	if hero:
		if location:
			article = "an" if ("off" in location) else "a"
			phrases.extend([f"as {article}", location, hero])
		else:
			phrases.append("as " + hero)
	elif location:
		location = location.replace("ing", "er")
		phrases.append("as " + location)
	if item:
		phrases.append("with a " + item)

	# post-match stuff
	phrases.append(get_context(LocalizationContext.PostMatch))

	# with/without context stuff
	phrases.append(get_context(LocalizationContext.WhoWith))

	return " ".join(filter(lambda p: p is not None, phrases))


def create_matchfilter_args(inter: disnake.CmdInter):
	return [
		QueryArg("win", [
				ArgOption(1, "won", r"wins?|won|victory"),
				ArgOption(0, "lost", r"loss|lose|lost|losses|defeat")
			],
			check_filter=CheckFilter(None, lambda m, v: (m.get('radiant_win') == (m.get('player_slot') < 128)) == (v == 1))
		),
		QueryArg("is_radiant", [
				ArgOption(1, f"on the {LOCALIZE_HIGHLIGHT_WRAPPER}radiant{LOCALIZE_HIGHLIGHT_WRAPPER} team", r"(as|on)? ?radiant"),
				ArgOption(0, f"on the {LOCALIZE_HIGHLIGHT_WRAPPER}dire{LOCALIZE_HIGHLIGHT_WRAPPER} team", r"(as|on)? ?dire")
			],
			check_filter=CheckFilter(None, lambda m, v: (m.get('player_slot') < 128) == (v == 1)),
			localization_context=LocalizationContext.PostMatch
		),
		QueryArg("lobby_type", [
				ArgOption(7, "ranked", r"ranked"),
				ArgOption(0, "non-ranked", r"(un|non)-?ranked")
			],
			localization_context=LocalizationContext.PreMatch
		), 
		QueryArg("significant", [
				ArgOption(1, "all-pick", r"(significant|standard)"),
				ArgOption(0, None, r"(not|non|in|un)(-| )?(significant|standard)")
			],
			check_filter=CheckFilter(None, lambda m, v: (v == 0) or (m.get('game_mode') in [1, 22])),
			localization_context=LocalizationContext.PreMatch
		),
		QueryArg("game_mode",
			get_cache_game_mode_arg_options(),
			localization_context=LocalizationContext.PreMatch
		),
		QueryArg("region",
			get_cache_region_arg_options(),
			localization_context=LocalizationContext.PreMatch
		),
		TimeSpanArg(inter,
			localization_context=LocalizationContext.PostMatch), # TODO: figure out how to specify that this should ONLY use the postfilter for CheckFilter
		QueryArg("offset", [
				ArgOption(lambda m: int(m.group(1)), "(skip {value} matches)", r"(?:skip|offset) ?(\d{1,3})"),
			],
			localization_context=LocalizationContext.WhoWith
		),
		QueryArg("limit", [
				ArgOption(lambda m: int(m.group(1)), "{value}", r"(?:limit|count|show)? ?(\d{1,3})")
			],
			check_filter=CheckFilter(None, lambda m, v: True)
		),
		QueryArg("party_size", [
				ArgOption(1, "solo", r"solo"),
			],
			localization_context=LocalizationContext.PreMatch,
			localization_index=-1
		),
		QueryArg("_inparty", [
				ArgOption(True, "party", r"((in|with)? (a )?)?(party|group|friends|team)"),
			], PostFilter("party_size", lambda p: (p.get("party_size", 0) or 0) > 1),
			localization_context=LocalizationContext.PreMatch,
			localization_index=-1
		),
		QueryArg("lane_role", [
				ArgOption(1, "safelane", r"safe( ?lane)?"),
				ArgOption(2, "mid", r"mid(dle)?( ?lane)?"),
				ArgOption(3, "offlane", r"(off|hard)( ?lane)?"),
				ArgOption(4, "jungling", r"jungl(e|ing)"),
			], PostFilter("is_roaming", lambda p: p.get("is_roaming") == False),
			localization_context=LocalizationContext.PlayerLocation
		),
		QueryArg("_roaming", [
				ArgOption(True, "roaming", r"roam(ing)?|gank(ing)?"),
			], PostFilter("is_roaming", lambda p: p.get("is_roaming") == True),
			localization_context=LocalizationContext.PlayerLocation
		),
		QueryArg("_parsed", [
				ArgOption(True, "parsed", r"(is)?( |_)?parsed"),
			], PostFilter("version", lambda p: p.get("version") is not None),
			localization_context=LocalizationContext.PreMatch,
			localization_index=-2
		),
		PlayerArg(inter, "included_account_id", "with ",
			localization_context=LocalizationContext.WhoWith),
		PlayerArg(inter, "excluded_account_id", "without ",
			localization_context=LocalizationContext.WhoWith),
		ItemArg(inter, "_item"),
		HeroArg(inter, "with_hero_id", "(?:with|alongside) ",
			localization_template="alongside a {}",
			localization_context=LocalizationContext.WhoWith),
		HeroArg(inter, "against_hero_id", "(?:against|vs) ",
			localization_template="vs a {}",
			localization_context=LocalizationContext.WhoWith),
		HeroArg(inter, "hero_id", "(?:as )?"),
		PlayerArg(inter, "_player", "")
	]


class MatchFilter():
	def __init__(self, args=None):
		self.args = args or []
		self.projections = []

	@classmethod
	async def init(cls, matchfilter, inter):
		if matchfilter is None:
			matchfilter = await MatchFilter.convert(inter, "")
		return matchfilter

	@commands.converter_method
	async def convert(cls, inter: disnake.CmdInter, argument: str):
		await safe_defer(inter)
		parser = InputParser(argument)
		args = create_matchfilter_args(inter)
		for arg in args:
			value = parser.take_regex(arg.regex())
			if value:
				await arg.parse(value)
		for level in [ 2 ]:
			for arg in args:
				if arg.parse_levels >= level and not arg.has_value():
					value = parser.take_regex(arg.regex(level=level))
					if value:
						await arg.parse(value, level=level)

		playerarg = MatchFilter._get_arg(args, "_player")
		if playerarg.player is None:
			playerarg.set_player(await DotaPlayer.from_author(inter))
		if (MatchFilter._get_arg(args, "game_mode").has_value()): # custom thing to make sure to not hide unsignificant things
			MatchFilter._get_arg(args, "significant").value = 0
		if parser.text:
			raise CustomBadArgument(UserError(f"I'm not sure what you mean by '{parser.text}'"))
		return cls(args)

	def __str__(self):
		return self.to_query_args() if len(self.args) > 0 else "None"

	@property
	def hero(self):
		for arg in self.args:
			if arg.name == "hero_id":
				return arg.hero
		return None

	@property
	def player(self):
		for arg in self.args:
			if arg.name == "_player":
				return arg.player
		return None

	def has_value(self, name):
		for arg in self.args:
			if arg.name == name:
				return arg.has_value()
		return False

	@classmethod
	def _get_arg(cls, args, name):
		for arg in args:
			if arg.name == name:
				return arg
		return None

	def get_arg(self, name):
		arg = MatchFilter._get_arg(self.args, name)
		return None if arg is None else arg.value

	def set_arg(self, name, value, overwrite=True):
		if (not self.has_value(name)) or overwrite:
			for arg in self.args:
				if arg.name == name:
					arg.value = value
					return
			self.args.append(SimpleQueryArg(name, value))

	def add_projections(self, projections):
		self.projections.extend(projections)

	def to_query_args(self, for_web_url=False):
		args = filter(lambda a: a.has_value() and a.name and not a.name.startswith("_"), self.args)
		args = list(map(lambda a: a.to_query_arg(), args))
		if not for_web_url:
			projections = self.projections
			for arg in self.args:
				if arg.has_value() and arg.post_filter:
					if isinstance(arg.post_filter.key, list):
						projections.extend(arg.post_filter.key)
					else:
						projections.append(arg.post_filter.key)
			if len(projections) > 0:
				args.extend(map(lambda p: f"project={p}", projections))
			if self.is_post_filter_required(): # if we need post_filter, limit & offset afterwards
				if self.has_value("limit"):
					args.remove(MatchFilter._get_arg(self.args, "limit").to_query_arg())
				if self.has_value("offset"):
					args.remove(MatchFilter._get_arg(self.args, "offset").to_query_arg())
		return "&".join(args)

	# whether or not this query will only return parsed games
	def is_only_parsed(self):
		parsed_args_list = [ "lane", "lane_role", "_roaming", "_version" ]
		return any(self.has_value(key) for key in parsed_args_list)

	def post_filter(self, matches):
		if self.is_post_filter_required():
			matches = list(filter(lambda m: all(a.check_post_filter(m) for a in self.args), matches))
			if self.has_value("offset"):
				offset_value = self.get_arg("offset")
				if len(matches) <= offset_value:
					matches = []
				else:
					matches = matches[offset_value:]
			if self.has_value("limit") and len(matches) > self.get_arg("limit"):
				matches = matches[0:self.get_arg("limit")]
		return matches

	def is_post_filter_required(self):
		for arg in self.args:
			if arg.has_value() and arg.post_filter is not None:
				return True
		return False
	
	def localize(self, matches = None):
		return localize_matchfilter(self, matches)

	def to_query_url(self):
		args = self.to_query_args()
		return f"/players/{self.player.steam_id}/matches?{args}"


class HeroStatArg(QueryArg):
	def __init__(self, inter, name):
		super().__init__(name)
		dotabase = inter.bot.get_cog("Dotabase")
		self.patterns = get_cache_hero_stats_patterns(dotabase)

	def regex(self):
		return self.patterns["all"]

	async def parse(self, text):
		for stat, pattern in self.patterns.items():
			if stat != "all" and re.match(pattern, text):
				self.value = stat
				return self.value


class HeroStatsTableArgs():
	def __init__(self, kwargs):
		self.stat = kwargs.get("stat")
		self.hero_level = kwargs.get("hero_level", 1)
		self.hero_count = kwargs.get("hero_count", 20)
		self.reverse = kwargs.get("reverse", False)

	@classmethod
	async def convert(cls, inter, argument):
		parser = InputParser(argument)
		args = [
			QueryArg("hero_count", {
				r"(?:hero ?)?(?:limit|count|show) (\d+)": lambda m: int(m.group(1))
			}),
			QueryArg("hero_level", {
				r"(?:lvl|level)? ?(\d\d?)": lambda m: int(m.group(1))
			}),
			QueryArg("reverse", {
				r"rev(erse)?|desc(ending)?|least-?(most)?": True
			}),
			HeroStatArg(inter, "stat")
		]
		kwargs = {}
		for arg in args:
			value = parser.take_regex(arg.regex())
			if value:
				await arg.parse(value)
				kwargs[arg.name] = arg.value
		if parser.text:
			raise CustomBadArgument(UserError(f"I'm not sure what you mean by '{parser.text}'"))
		return cls(kwargs)
