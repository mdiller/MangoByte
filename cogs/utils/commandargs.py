from __main__ import settings, botdata, httpgetter
import re
import discord
from discord.ext import commands
from .helpers import *
from collections import OrderedDict


hero_pattern_cache = {}
def get_cache_hero_pattern(dotabase, prefix):
	if prefix in hero_pattern_cache:
		return hero_pattern_cache[prefix]
	else:
		pattern = f"{prefix}{dotabase.hero_regex}"
		pattern = f"\\b(?:{pattern})\\b"
		pattern = re.compile(pattern, re.IGNORECASE)
		hero_pattern_cache[prefix] = pattern
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


def clean_input(t):
	return re.sub(r'[^a-z1-9\s]', r'', str(t).lower())

class SteamNotLinkedError(UserError):
	def __init__(self, user=None):
		self.is_author = user is None
		self.user = user
		if not self.is_author:
			super().__init__(f"{user.name} doesn't have a steam account linked. They should try `{{cmdpfx}}userconfig steam` to see how to link their steam account.")
		else:
			super().__init__("Yer steam account isn't linked to yer discord account yet.\nTry doin `{cmdpfx}userconfig steam` to see how to link a steam account.")

class NoMatchHistoryError(UserError):
	def __init__(self, steam_id):
		super().__init__(f"")
		self.embed = discord.Embed(description=f"It looks like you either haven't played dota on this account, or the matches you've played are hidden. If you've played matches on this account, you should try enabling the **Expose Public Match Data** option in dota (see image below). Once you've done that, go to [your opendota profile](http://www.opendota.com/players/{steam_id}) and click the button under your name that says **REFRESH**")
		self.file = discord.File(settings.resource("images/expose_match_data.png"), "tip.png")
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
	async def from_author(cls, ctx):
		return await cls.convert(ctx, None)

	@classmethod
	async def convert(cls, ctx, player):
		is_author = player is None
		if is_author:
			player = ctx.message.author

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
			return cls(player, f"[{player_info['profile']['personaname']}](https://www.opendota.com/players/{player})", is_author)

		if not isinstance(player, discord.User):
			try:
				player = await commands.MemberConverter().convert(ctx, str(player))
			except commands.BadArgument:
				raise CustomBadArgument(UserError("Ya gotta @mention a user who has been linked to a steam id, or just give me a their steam id"))

		userinfo = botdata.userinfo(player.id)
		if userinfo.steam is None:
			if is_author:
				raise CustomBadArgument(SteamNotLinkedError())
			else:
				raise CustomBadArgument(SteamNotLinkedError(player))
		return cls(userinfo.steam, player.mention, is_author)

class QueryArg():
	def __init__(self, name, args_dict=None, post_filter=None):
		self.name = name
		self.args_dict = args_dict or {}
		self.value = None
		self.post_filter = None

	async def parse(self, text):
		for key in self.args_dict:
			match = re.match(key, text)
			if match:
				value = self.args_dict[key]
				if callable(value):
					value = value(match)
				self.value = value

	def has_value(self):
		return self.value is not None

	def regex(self):
		return "|".join(map(lambda k: f"(?:{k})", self.args_dict.keys()))

	def to_query_arg(self):
		return f"{self.name}={self.value}"

	def check_post_filter(self, p):
		if (not self.has_value()) or (self.post_filter is None):
			return True
		return self.post_filter(p)

# added manually
class SimpleQueryArg(QueryArg):
	def __init__(self, name, value):
		super().__init__(name)
		self.value = value


class TimeSpanArg(QueryArg):
	def __init__(self):
		super().__init__("date")
		self.count = None
		self.chunk = None

	async def parse(self, text):
		match = re.match(self.regex(), text)
		self.count = int(match.group(2) or "1")
		self.chunk = match.group(3)
		self.value = self.days

	@property
	def days(self):
		count = {
			"today": 1,
			"day": 1,
			"week": 7,
			"month": 30,
			"year": 365
		}[self.chunk]
		return count * self.count

	def regex(self):
		return r"(?:in|over)? ?(?:the )?(this|last|past)? ?(\d+)? ((?:to)?day|week|month|year)s?"

class HeroArg(QueryArg):
	def __init__(self, ctx, name, prefix):
		super().__init__(name)
		self.prefix = prefix
		self.dotabase = ctx.bot.get_cog("Dotabase")
		self.hero = None

	def regex(self):
		return get_cache_hero_pattern(self.dotabase, self.prefix)

	async def parse(self, text):
		text = re.sub(self.prefix, "", text, flags=re.IGNORECASE)
		self.hero = self.dotabase.lookup_hero(text)
		self.value = self.hero.id

class PlayerArg(QueryArg):
	def __init__(self, ctx, name, prefix):
		super().__init__(name)
		self.ctx = ctx
		self.prefix = prefix
		self.player = None

	def regex(self):
		pattern = "(<@[!&]?[0-9]+>|\d+)"
		if self.prefix == "":
			return re.compile(pattern)
		return f"{self.prefix}{pattern}"

	def set_player(self, player):
		self.player = player
		self.value = player.steam_id

	async def parse(self, text):
		text = re.sub(self.prefix, "", text, flags=re.IGNORECASE)
		self.set_player(await DotaPlayer.convert(self.ctx, text))

class MatchFilter():
	def __init__(self, args=None):
		self.args = args or []
		self.projections = []

	@classmethod
	async def init(cls, matchfilter, ctx):
		if matchfilter is None:
			matchfilter = await MatchFilter.convert(ctx, "")
		return matchfilter

	@classmethod
	async def convert(cls, ctx, argument):
		parser = InputParser(argument)
		args = [
			QueryArg("win", {
				r"wins?|won|victory": 1,
				r"loss|lost|losses|defeat": 0
			}),
			QueryArg("is_radiant", {
				r"(as|on)? ?radiant": 1,
				r"(as|on)? ?dire": 0
			}),
			QueryArg("lobby_type", {
				r"ranked": 7,
				r"(un|non)-?ranked": 0
			}),
			QueryArg("significant", {
				r"(significant|standard)": 1,
				r"(not|non)(-| )?(significant|standard)": 0
			}),
			QueryArg("limit", {
				r"(?:limit|count|show) (\d+)": lambda m: int(m.group(1))
			}),
			QueryArg("lane_role", {
				r"safe( ?lane)?": 1,
				r"mid(dle)?( ?lane)?": 2,
				r"(off|hard)( ?lane)?": 3,
				r"jungl(e|ing)": 4
			}, lambda p: not p.get("is_roaming")),
			QueryArg(None, {
				r"roam(ing)?|gank(ing)?": True
			}, lambda p: p.get("is_roaming")),
			TimeSpanArg(),
			PlayerArg(ctx, "included_account_id", "with "),
			PlayerArg(ctx, "excluded_account_id", "without "),
			HeroArg(ctx, "against_hero_id", "(?:against|vs) "),
			HeroArg(ctx, "with_hero_id", "with "),
			HeroArg(ctx, "hero_id", "(?:as )?"),
			PlayerArg(ctx, "_player", "")
		]
		for arg in args:
			value = parser.take_regex(arg.regex())
			if value:
				await arg.parse(value)
		playerarg = MatchFilter._get_arg(args, "_player")
		if playerarg.player is None:
			playerarg.set_player(await DotaPlayer.from_author(ctx))
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

	def to_query_args(self):
		args = filter(lambda a: a.has_value() and a.name and not a.name.startswith("_"), self.args)
		args = list(map(lambda a: a.to_query_arg(), args))
		if len(self.projections) > 0:
			args.extend(map(lambda p: f"project={p}", self.projections))
		return "&".join(args)

	def post_filter(self, p):
		return all(a.post_filter_check() for a in self.args)

	def to_query_url(self):
		args = self.to_query_args()
		return f"/players/{self.player.steam_id}/matches?{args}"


class HeroStatArg(QueryArg):
	def __init__(self, ctx, name):
		super().__init__(name)
		dotabase = ctx.bot.get_cog("Dotabase")
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
	async def convert(cls, ctx, argument):
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
			HeroStatArg(ctx, "stat")
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