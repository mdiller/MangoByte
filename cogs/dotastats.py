import asyncio
import datetime
import math
import os
import re
import statistics
import time
from types import *
from enum import Enum
from collections import OrderedDict

import aiohttp
import disnake
import utils.drawing.dota as drawdota
import utils.drawing.graph as drawgraph
from disnake.ext import commands
from utils.command.commandargs import *
from utils.other.metastats import get_total_pro_games
from utils.tools.globals import botdata, httpgetter, logger, settings
from utils.tools.helpers import *

from cogs.mangocog import *


class MatchNotParsedError(UserError):
	def __init__(self, match_id, action=None):
		self.action = action if action else "do that"
		super().__init__(f"This match must be parsed before I can {self.action}.\nTry `/parse {match_id}` to request a parse.")

class StratzMatchNotParsedError(UserError):
	def __init__(self, match_id):
		super().__init__(f"It looks like match `{match_id}` hasn't been parsed by STRATZ. To have your matches parsed by STRATZ a bit faster, you can login to their site: <https://stratz.com>")

class InvalidMatchIdError(UserError):
	def __init__(self, match_id):
		super().__init__(f"Sorry, looks like `{match_id}` isn't a valid match id")

class MatchNotFoundError(UserError):
	def __init__(self, matchfilter):
		embed = disnake.Embed()
		embed.title = "No Matches Found"
		embed.description = matchfilter.localize([])
		embed.description += "\n\nNo matches found!"
		super().__init__(message="", embed=embed)

opendota_html_errors = {
	404: "Dats not a valid query. Take a look at the OpenDota API Documentation: https://docs.opendota.com",
	521: "[http error 521] Looks like the OpenDota API is down or somethin, so ya gotta wait a sec",
	502: "[http error 502] The OpenDota API is having some trouble connecting to Steam. Try again in a bit",
	"default": "OpenDota said we did things wrong 😢. http status code: {}"
}

graphtypes = {
	"Team Gold/Experience Difference": "teamdiff",
	"Player Gold": "playergold"
}

default_steam_icon = "https://steamcdn-a.akamaihd.net/steamcommunity/public/images/avatars/fe/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"

# converter for a single dota match
class DotaMatch():
	def __init__(self, match, steamid):
		self.match = match
		self.steamid = steamid
	
	@commands.converter_method
	async def convert(cls, inter: disnake.CmdInter, match_string: str):
		steamid = None

		if match_string.isnumeric():
			try:
				match = await get_match(match_string)
				return cls(match, steamid)
			except InvalidMatchIdError as e:
				pass # ignore this and continue, they probably passed in a steam id

		if match_string in [ "lm", "lastmatch", "last", "me" ]:
			match_string = "" # this way the converter will look at the author
		
		try:
			matchfilter = await MatchFilter.convert(inter, str(match_string))
			if matchfilter.player:
				steamid = matchfilter.player.steam_id
			match_id = await get_lastmatch_id(matchfilter)
			match = await get_match(match_id)
			return cls(match, steamid)
		except CustomBadArgument as e:
			raise UserError(f"Couldn't find a match_id or a player when given '{match_string}'")
		

def opendota_query_get_url(querystring):
	if settings.odota:
		if "?" in querystring:
			querystring += f"&api_key={settings.odota}"
		else:
			querystring += f"?api_key={settings.odota}"
	return f"https://api.opendota.com/api{querystring}"

async def opendota_query(querystring, cache=False):
	url = opendota_query_get_url(querystring)
	return await httpgetter.get(url, cache=cache, errors=opendota_html_errors)

async def opendota_query_filter(matchfilter):
	matches = await opendota_query(matchfilter.to_query_url())
	matches = matchfilter.post_filter(matches)
	return matches

# rate_limit = false if this is the only query we're sending
async def get_match(match_id):
	url = opendota_query_get_url(f"/matches/{match_id}")
	cached_data = await httpgetter.cache.get(url, "json")

	def check_valid_match(match_data):
		if match_data.get('radiant_win', True) is None:
			raise InvalidMatchIdError(match_id)
	
	if cached_data:
		if is_parsed(cached_data):
			check_valid_match(cached_data)
			return cached_data
		else:
			await httpgetter.cache.remove(url)

	try:
		data = await httpgetter.get(url, cache=True, errors=opendota_html_errors)
		check_valid_match(data)
		return data
	except HttpError as e:
		if e.code == 404:
			await httpgetter.cache.remove(url)
			raise InvalidMatchIdError(match_id)
		else:
			raise 


# rate_limit = false if this is the only query we're sending
async def get_stratz_match(match_id):
	if settings.stratz is None:
		raise UserError("Stratz not configured properly. The bot owner has gotta put the stratz api key in the config file")

	url = f"https://api.stratz.com/api/v1/match/{match_id}"
	cached_data = await httpgetter.cache.get(url, "json")
	
	if cached_data:
		if is_stratz_parsed(cached_data):
			return cached_data
		else:
			await httpgetter.cache.remove(url)

	try:
		headers = { 
			"Authorization": f"Bearer {settings.stratz}",
			"User-Agent": "STRATZ_API"
		}
		return await httpgetter.get(url, cache=True, errors={
			500: "Looks like something wrong with the STRATZ api",
			204: "STRATZ hasn't recieved this match yet. Try again a bit later",
			403: "got some weird auth error"
		}, headers=headers)
	except aiohttp.ClientConnectorError:
		logger.info("ClientConnectorError on stratz api result")
		raise StratzMatchNotParsedError(match_id)

def no_matches_found_response(matchfilter):
	embed = disnake.embed()

async def get_lastmatch_id(matchfilter, reverse=False):
	no_filter = matchfilter.to_query_args() == ""
	matchfilter.set_arg("significant", 0, False)
	if not reverse:
		matchfilter.set_arg("limit", 1)
	matches = await opendota_query_filter(matchfilter)
	if matches:
		if reverse:
			return matches[-1]["match_id"]
		else:
			return matches[0]["match_id"]
	else:
		if no_filter:
			raise NoMatchHistoryError(matchfilter.player.steam_id)
		else:
			raise MatchNotFoundError(matchfilter)


def s_if_plural(text, n):
	return text + "s" if n > 1 else text

def pretty_list(l, none=None):
	if len(l) == 0:
		return none
	if len(l) == 1:
		return l[0]
	elif len(l) == 2:
		return l[0] + " and " + l[1]
	else:
		l[-1] = "and " + str(l[-1])
		return ", ".join(l)

def get_pretty_time(seconds):
	seconds = abs(seconds)
	if seconds == 0:
		return None
	times = [
		["{t} second{s}", 60],
		["{t} minute{s}", 60],
		["{t} hour{s}", 24],
		["{t} day{s}", 30.416666666666], # Won't be exactly correct
		["{t} month{s}", 12],
		["{t} year{s}", 100],
	]
	result = []
	divisor = 1
	for time in times:
		t = int((seconds // divisor) % time[1])
		if t > 0:
			result.insert(0, time[0].format(t=t, s="s" if t > 1 else ""))
		divisor *= time[1]
	return pretty_list(result)

def get_pretty_duration(duration, postfix=True):
	if duration == 0:
		return "the exact start of the game"
	is_after = duration > 0
	result = get_pretty_time(duration)
	if postfix:
		result += " in" if is_after else " before the game started"
	return result


def is_parsed(match):
	return match.get("version", None) is not None


def is_stratz_parsed(match):
	return match.get("parsedDateTime") and match["players"][0].get("playbackData") and match["players"][0].get("playbackData").get("playerUpdatePositionEvents")

def format_teamfight(teamfight):
	if teamfight['our_dead'] is None and teamfight['their_dead'] is None:
		format_str = "There was a teamfight with no deaths"
	elif teamfight['our_dead'] is None:
		format_str = "We killed their {their_dead} without losing anyone"
	elif teamfight['their_dead'] is None:
		format_str = "We lost our {our_dead} and couldn't kill any of them"
	else:
		format_str = "We traded our {our_dead} for {their_dead}"
	format_str += ", resulting in a net {gain_loss} of {net_change:,} gold"
	return format_str.format(**teamfight)


def _match_avg(player_matches, key, round_place=0):
	x = 0
	total_count = 0
	for player in player_matches:
		if isinstance(key, LambdaType):
			val = key(player)
		else:
			if player.get(key) is None:
				continue
			val = player.get(key, 0)
		x += val
		total_count += 1
	if total_count == 0:
		return None
	x = round(x / total_count, round_place)
	return int(x) if round_place == 0 else x

def _match_percent(player_matches, key, round_place=0, needs_key=None):
	count = 0
	total_count = 0
	for player in player_matches:
		if needs_key and player.get(needs_key) is None:
			continue
		if isinstance(key, LambdaType):
			success = key(player)
		else:
			success = player.get(key, 0)
		if success:
			count += 1
		total_count += 1
	if total_count == 0:
		return None
	if round_place == "floor":
		count = math.floor((count * 100) / total_count)
		round_place = 0
	else:
		count = round((count * 100) / total_count, round_place)
	value = int(count) if round_place == 0 else count
	return f"{value}%"


class DotaStats(MangoCog):
	"""Commands for displaying information about Dota 2 players and matches

	Most of the data for this is collected through the [OpenDota API](https://docs.opendota.com/)"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.embed_color = disnake.Color.teal()
		dotabase = self.bot.get_cog("Dotabase")
		if not dotabase:
			raise ImportError("The Dotabase cog must be added before the DotaStats cog")
		self.dota_game_strings = read_json(settings.resource("json/dota_game_strings.json"))
		self.hero_info = dotabase.get_hero_infos()
		self.lookup_hero = dotabase.lookup_hero
		self.chat_wheel_info = dotabase.get_chat_wheel_infos()
		self.dota_gif_lock = asyncio.Lock()
	
	def get_hero_info(self, hero_id: int):
		if hero_id in self.hero_info:
			return self.hero_info[hero_id]
		return self.hero_info[0]

	async def get_meta_json(self): 
		url = 'https://api.opendota.com/api/herostats'
		return await httpgetter.get(url)

	def sort_meta(self, json, num=10): 
		"""re-orders the meta json based on pick/ban + winrate.
		num = number of top heroes to include """
		total_games = get_total_pro_games(json)
		json = list(filter(lambda x: x.get('pro_pick', 1) > 0, json))
		sorted_json = sorted(
			json, 
			reverse=True, 
			# sorts by (winrate) + (pick/ban rate)
			key=lambda x: (((x.get('pro_pick', 0) + x.get('pro_ban', 0)) / total_games)
			+ ((x.get('pro_win', 0) / x.get('pro_pick', 1)))),
			)
		if num > 0: 
			return sorted_json[:num]
		return sorted_json

	def get_pretty_hero(self, player, use_icons=False):
		dotabase = self.bot.get_cog("Dotabase")
		hero_info = self.get_hero_info(player["hero_id"])
		name = hero_info["name"]
		if use_icons:
			emoji = hero_info["emoji"]
			return f"{emoji}**{name}**"
		return f"**{name}**"

	def get_player_rank(self, playerinfo):
		# gets the players rank information as a string with a rank emoticaon
		rank_strings = [ "Unranked", "Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal" ]

		base_rank_tier = playerinfo.get("rank_tier")
		if base_rank_tier is None:
			base_rank_tier = 0
		rank_tier = base_rank_tier // 10
		leaderboard_rank = playerinfo.get("leaderboard_rank")
		rank_string = f"**{rank_strings[rank_tier]}**"
		stars = min(base_rank_tier % 10, 7)
		if stars > 0:
			rank_string += f" [{stars}]"
		on_leaderboard = rank_tier >= 7 and leaderboard_rank
		if on_leaderboard:
			rank_string = f"**Immortal** [Rank {leaderboard_rank}]"
			rank_tier = 8

		emoji_id = f"rank_{rank_tier}"
		if on_leaderboard:
			if leaderboard_rank <= 10:
				emoji_id += "c"
			elif leaderboard_rank <= 100:
				emoji_id += "b"

		rank_string = self.get_emoji(emoji_id) + " " + rank_string

		return rank_string

	async def get_player_mention(self, steamid, ctx_inter: InterContext):
		# expects that steamid is a valid int
		player = await DotaPlayer.convert(ctx_inter, steamid)
		return player.mention

	async def create_dota_gif(self, match, stratz_match, start_time, end_time, ms_per_second=100):
		await self.dota_gif_lock.acquire()
		try:
			result = await drawdota.create_dota_gif(self.bot, match, stratz_match, start_time, end_time, ms_per_second)
		finally:
			self.dota_gif_lock.release()
		return result

	async def get_teamfights(self, game, is_radiant):
		teamfights = []
		for teamfight in game['teamfights']:
			net_gain = 0
			our_dead = []
			their_dead = []
			num_players = min([ len(teamfight['players']), len(game['players']) ])
			for i in range(0, num_players):
				deadtext = self.get_pretty_hero(game['players'][i])
				if teamfight['players'][i]['deaths'] == 0:
					deadtext = None
				elif teamfight['players'][i]['deaths'] > 1:
					deadtext += "(x{})".format(teamfight['players'][i]['deaths'])

				if (game['players'][i]['isRadiant'] == is_radiant): # on our team
					net_gain += teamfight['players'][i]['gold_delta']
					if deadtext:
						our_dead.append(deadtext)
				else:
					net_gain -= teamfight['players'][i]['gold_delta']
					if deadtext:
						their_dead.append(deadtext)
			teamfight_dict = {
					"gain_loss": "gain" if net_gain >= 0 else "loss",
					"our_dead": pretty_list(our_dead, None),
					"their_dead": pretty_list(their_dead, None),
					"net_change": abs(net_gain),
					"deaths": teamfight['deaths'],
					"time": teamfight['start'],
					"time_end": teamfight['end']
				}
			teamfight_dict['formatted'] = format_teamfight(teamfight_dict)
			teamfights.append(teamfight_dict)
		return teamfights

	async def get_firstblood_story(self, game, is_radiant):
		fb_objective = next((obj for obj in game['objectives'] if obj['type'] == "CHAT_MESSAGE_FIRSTBLOOD"), None)
		if fb_objective is None:
			return "" # No first blood this game, or it wasnt reported in objectives log
		fb_log = None
		fb_killer = next(p for p in game['players'] if p['player_slot'] == fb_objective['player_slot'])
		fb_log = next((kill for kill in fb_killer['kills_log'] if kill['time'] == fb_objective['time']), None)
		if fb_log is None:
			return "" # Can't find the kill log of when first blood happened
		dotabase = self.bot.get_cog("Dotabase")
		fb_victim_id = next((h for h in self.hero_info if self.get_hero_info(h)['full_name'] == fb_log['key']), None)
		fb_victim = next((p for p in game['players'] if p['hero_id'] == fb_victim_id), None)
		if fb_victim is None or fb_victim_id is None:
			return "First blood involved a new hero. (oooo mysterious. I gotta update dotabase prolly)"

		return "First blood was drawn when {} {} killed {} {} at {}\n\n".format(
			"our" if (fb_killer['isRadiant'] == is_radiant) else "their",
			self.get_pretty_hero(fb_killer),
			"our" if (fb_victim['isRadiant'] == is_radiant) else "their",
			self.get_pretty_hero(fb_victim),
			get_pretty_duration(fb_objective['time']))


	async def get_teamfight_stories(self, game, is_radiant):
		teamfights = await self.get_teamfights(game, is_radiant)
		teamfights_count = len(teamfights)
		story = ""

		timeline = []
		most_deaths_fights = 2
		most_change_fights = 2
		if len(teamfights) > most_deaths_fights + most_change_fights:
			# do calcs
			teamfights = sorted(teamfights, key=lambda t: t['net_change'], reverse=True)
			for i in range(0, most_change_fights):
				timeline.append(teamfights.pop(0))
			teamfights = sorted(teamfights, key=lambda t: t['deaths'], reverse=True)
			for i in range(0, most_deaths_fights):
				timeline.append(teamfights.pop(0))
		else:
			timeline.extend(teamfights)
			teamfights = []

		timeline = sorted(timeline, key=lambda t: t['time'])
		return list(map(lambda t: t["formatted"], timeline))

	async def get_lane_story(self, players, laneid, is_radiant, use_icons=False):
		our_eff = 0
		their_eff = 0
		our_heroes = []
		their_heroes = []
		for player in players:
			if player['lane'] == laneid and not player.get('is_roaming', False):
				if (player['isRadiant'] == is_radiant): #on our team
					if player.get('lane_efficiency', 0) > our_eff:
						our_eff = player['lane_efficiency']
					our_heroes.append(self.get_pretty_hero(player, use_icons))
				else: #on their team
					if player.get('lane_efficiency', 0) > their_eff:
						their_eff = player['lane_efficiency']
					their_heroes.append(self.get_pretty_hero(player, use_icons))
		return {
			"us": pretty_list(our_heroes, "An empty lane"),
			"won_lost": "won" if our_eff > their_eff else "lost",
			"them": pretty_list(their_heroes, "an empty lane")
		}

	# gets the story for all of the lanes
	async def get_lane_stories(self, game, is_radiant, use_icons=False):
		story = ""
		lanes = {1: "bottom", 2: "middle", 3: "top"}
		for laneid in lanes:
			story += "• {0[us]} {0[won_lost]} {1} lane vs {0[them]}\n".format(await self.get_lane_story(game['players'], laneid, is_radiant, use_icons), lanes[laneid])
		roamers = [self.get_pretty_hero(p, use_icons) for p in game['players'] if p.get('is_roaming')]
		if roamers:
			story += f"• {pretty_list(roamers)} roamed\n"
		return story

	def set_match_footer(self, match, embed):
		dotabase = self.bot.get_cog("Dotabase")
		footer_text = str(match["match_id"])
		patch = dotabase.get_match_patch(match)
		if patch:
			footer_text += " • " + patch
		embed.set_footer(text=footer_text)
		embed.timestamp = datetime.datetime.fromtimestamp(match['start_time'], tz=datetime.timezone.utc)

	# prints the stats for the given player's latest game
	async def player_match_stats(self, steamid, match, inter, description_intro=None):
		# Finds the player in the game which has our matching steam32 id
		match_id = match["match_id"]
		player = None
		if steamid:
			player = next((p for p in match['players'] if p.get('account_id') == steamid), None)
		if player is None:
			await self.print_match_stats(inter, match)
			return

		hero_info = self.get_hero_info(player['hero_id'])
		hero_name = hero_info['name']

		duration = get_pretty_duration(match['duration'], postfix=False)
		winstatus = "Won" if player["win"] != 0 else "Lost"
		game_mode = self.dota_game_strings.get(f"game_mode_{match.get('game_mode')}", "Unknown")
		lobby_type = self.dota_game_strings.get(f"lobby_type_{match.get('lobby_type')}", "Unknown") + " "
		if lobby_type == "Normal ":
			lobby_type = ""
		
		description = (f"{winstatus} a {lobby_type}**{game_mode}** match as {hero_name} in {duration}. "
					"More info at "
					+ (f"[Windrun](https://www.windrun.io/matches/{match_id}), " if game_mode == "Ability Draft" else "") +
					f"[DotaBuff](https://www.dotabuff.com/matches/{match_id}), "
					f"[OpenDota](https://www.opendota.com/matches/{match_id}), or "
					f"[STRATZ](https://www.stratz.com/match/{match_id})")
		
		if description_intro:
			description = description_intro + "\n\n" + description

		embed = disnake.Embed(description=description, color=self.embed_color)

		embed.set_author(name=player.get('personaname') or "Anonymous", icon_url=hero_info['icon'], url="https://www.opendota.com/players/{}".format(steamid))

		damage_format = "KDA: **{kills}**/**{deaths}**/**{assists}**\n"
		if player.get("hero_damage") is not None:
			damage_format += "Hero Damage: {hero_damage:,}\n"
		if player.get("hero_healing") is not None:
			damage_format += "Hero Healing: {hero_healing:,}\n"
		if player.get("tower_damage") is not None:
			damage_format += "Tower Damage: {tower_damage:,}\n"
		embed.add_field(name="Damage", value=damage_format.format(**player))

		if not player.get("total_gold"):
			player["total_gold"] = 0
		embed.add_field(name="Economy", value=(
			"Net Worth: {total_gold:,}\n"
			"Last Hits: {last_hits:,}\n"
			"Denies: {denies}\n"
			"Level: {level}\n".format(**player)))

		match_image = disnake.File(await drawdota.create_match_image(match), "match.png")
		embed.set_image(url=f"attachment://{match_image.filename}")

		self.set_match_footer(match, embed)

		await inter.send(embed=embed, file=match_image)

	@commands.slash_command()
	async def lm(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Gets info about the player's last dota game

		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'
		"""
		await self.safe_defer(inter)
		
		def matchfilterfixer(text):
			text = re.sub(r"^All", "The last", text)
			text = re.sub(r" matches ", " match ", text)
			return text

		description_intro = None if (not matchfilter) else matchfilterfixer(matchfilter.localize())
		matchfilter = await MatchFilter.init(matchfilter, inter)
		player = matchfilter.player

		match_id = await get_lastmatch_id(matchfilter)
		match = await get_match(match_id)
		await self.player_match_stats(player.steam_id, match, inter, description_intro)

	@commands.slash_command()
	async def firstmatch(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Gets info about the player's first dota game

		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'
		"""
		await self.safe_defer(inter)
		
		def matchfilterfixer(text):
			text = re.sub(r"^All", "The first", text)
			text = re.sub(r" matches ", " match ", text)
			return text

		description_intro = None if (not matchfilter) else matchfilterfixer(matchfilter.localize())
		matchfilter = await MatchFilter.init(matchfilter, inter)
		player = matchfilter.player

		match_id = await get_lastmatch_id(matchfilter, reverse=True)
		match = await get_match(match_id)
		await self.player_match_stats(player.steam_id, match, inter, description_intro)

	async def print_match_stats(self, inter, match):
		match_id = match["match_id"]
		duration = get_pretty_duration(match['duration'], postfix=False)
		game_mode = self.dota_game_strings.get(f"game_mode_{match.get('game_mode')}", "Unknown")
		lobby_type = self.dota_game_strings.get(f"lobby_type_{match.get('lobby_type')}", "Unknown") + " "
		if lobby_type == "Normal ":
			lobby_type = ""

		embed = disnake.Embed(color=self.embed_color)
		embed.description = (f"This {lobby_type}**{game_mode}** match ended in {duration} \n"
					"More info at "
					+ (f"[Windrun](https://www.windrun.io/matches/{match_id}), " if game_mode == "Ability Draft" else "") +
					f"[DotaBuff](https://www.dotabuff.com/matches/{match_id}), "
					f"[OpenDota](https://www.opendota.com/matches/{match_id}), or "
					f"[STRATZ](https://www.stratz.com/match/{match_id})")

		embed.set_author(name="Match {}".format(match_id), url="https://www.opendota.com/matches/{}".format(match_id))

		embed.add_field(name="Game Mode", value=game_mode)
		embed.add_field(name="Lobby Type", value=game_mode)

		match_image = disnake.File(await drawdota.create_match_image(match), filename="matchimage.png")
		embed.set_image(url=f"attachment://{match_image.filename}")

		self.set_match_footer(match, embed)

		await inter.send(embed=embed, file=match_image)

	# a header to be used for sub commands
	@commands.slash_command()
	async def match(self, inter: disnake.CmdInter):
		await self.safe_defer(inter)
		pass
	
	@match.sub_command(name="info")
	async def match_info(self, inter: disnake.CmdInter, match: DotaMatch):
		"""Creates a table with some basic stats and information about the dota match

		Parameters
		----------
		match: The ID of the match, a reference to a player, or 'lm'. See '/docs Match Argument` for more info
		"""
		await self.player_match_stats(match.steamid, match.match, inter)

	@match.sub_command(name="story")
	async def match_story(self, inter: disnake.CmdInter, match: DotaMatch, perspective: commands.option_enum(OrderedDict({"Radiant": "radiant", "Dire": "dire"})) = "radiant"):
		"""Tells the story of the match

		Parameters
		----------
		match: The ID of the match, a reference to a player, or 'lm'. See '/docs Match Argument` for more info
		perspective: The team who's perspective we should tell the match from
		"""
		steamid = match.steamid
		match = match.match

		if steamid is not None:
			player_data = next((p for p in match['players'] if p['account_id'] == steamid), None)
			if steamid is not None and player_data is not None:
				is_radiant = player_data['isRadiant']
				perspective = "{2}({0}, {1})".format(self.get_pretty_hero(player_data), "Radiant" if is_radiant else "Dire", player_data.get("personaname"))
			else:
				is_radiant = True
		elif perspective.lower() == "radiant":
			is_radiant = True
			perspective = None
		elif perspective.lower() == "dire":
			is_radiant = False
			perspective = None
		else:
			raise UserError("Perspective must be either radiant or dire")
		
		if not is_parsed(match):
			raise MatchNotParsedError(match["match_id"], "create a story")

		if not perspective:
			perspective = "The Radiant" if is_radiant else "The Dire"
			end_perspective = perspective
		else:
			end_perspective = f"{perspective} and their friends"

		story = (f"*Told from the perspective of {perspective}*\n"
				f"To see a more extensive story, try the [story tab](https://www.opendota.com/matches/{match['match_id']}/story) on opendota\n\n")

		story += await self.get_firstblood_story(match, is_radiant)

		story += await self.get_lane_stories(match, is_radiant)

		teamfights = await self.get_teamfight_stories(match, is_radiant)

		match_ending_state = "won" if (is_radiant == match['radiant_win']) else "lost"
		story_end = f"\n{end_perspective} {match_ending_state} the match at { get_pretty_duration(match['duration']) }"

		i = 0
		while i < len(teamfights) and (len(story) + len(teamfights[i]) + len(story_end)) < 2000:
			story += f"\n\n{teamfights[i]}"
			i += 1

		embed = disnake.Embed(description=story, color=self.embed_color)
		embed.title = f"Story of Match {match['match_id']}"
		embed.url = f"https://www.opendota.com/matches/{match['match_id']}/story"

		self.set_match_footer(match, embed)

		await inter.send(embed=embed)

	@commands.slash_command()
	async def recent(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Gets a list of your recent dota matches
    
		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'
		"""
		await self.safe_defer(inter)

		matchfilter = await MatchFilter.init(matchfilter, inter)

		steam32 = matchfilter.player.steam_id

		matchfilter.set_arg("limit", 10, False)
		matchfilter.set_arg("significant", 0, False)

		limit_max = 100
		if matchfilter.get_arg("limit") > limit_max or matchfilter.has_value("date"):
			matchfilter.set_arg("limit", limit_max, True)

		if matchfilter.get_arg("limit") < 1:
			raise UserError("Limit of matches can't be less than 1")

		hero = matchfilter.hero

		matchfilter.add_projections([ "kills", "deaths", "assists", "hero_id", "version", "game_mode", "lobby_type", "region", "duration", "start_time" ])

		matches = await opendota_query_filter(matchfilter)
		if not matches:
			raise MatchNotFoundError(matchfilter)

		matches = sorted(matches, key=lambda m: m.get("start_time"), reverse=True)


		embed = disnake.Embed()

		embed.title = "Matches"
		embed.url = f"https://www.opendota.com/players/{steam32}/matches"
		if hero:
			if hero.color:
				embed.color = disnake.Color(int(hero.color[1:], 16))
		query_args = matchfilter.to_query_args()
		if query_args:
			embed.url += "?" + query_args

		embed.description = matchfilter.localize(matches)

		matches_image = await drawdota.draw_matches_table(matches, self.dota_game_strings)
		matches_image = disnake.File(matches_image, "matches.png")
		embed.set_image(url=f"attachment://{matches_image.filename}")
		embed.set_footer(text=f"Try /matchids to get copy-pastable match ids")

		await inter.send(embed=embed, file=matches_image)

	@commands.slash_command()
	async def matchids(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Gets a list of recent matchids that match the given filter
    
		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'"""
		await self.safe_defer(inter)

		matchfilter = await MatchFilter.init(matchfilter, inter)

		steam32 = matchfilter.player.steam_id

		matchfilter.set_arg("limit", 10, False)
		matchfilter.set_arg("significant", 0, False)

		limit_max = 100
		if matchfilter.get_arg("limit") > limit_max or matchfilter.has_value("date"):
			matchfilter.set_arg("limit", limit_max, True)

		if matchfilter.get_arg("limit") < 1:
			raise UserError("Limit of matches can't be less than 1")

		matchfilter.add_projections([ "kills", "deaths", "assists", "hero_id", "version", "game_mode", "lobby_type", "region", "duration", "start_time" ])

		matches = await opendota_query_filter(matchfilter)
		if not matches:
			raise MatchNotFoundError(matchfilter)

		matches = sorted(matches, key=lambda m: m.get("start_time"), reverse=True)


		embed = disnake.Embed()

		embed.title = "Matches"
		embed.url = f"https://www.opendota.com/players/{steam32}/matches"
		query_args = matchfilter.to_query_args()
		if query_args:
			embed.url += "?" + query_args

		embed.description = matchfilter.localize(matches)

		embed.description += "\n\n```\n"
		embed.description += "\n".join(list(map(lambda m: str(m["match_id"]), matches)))
		embed.description += "\n```"

		embed.set_footer(text=f"Try /recent to get more details about these matches")

		await inter.send(embed=embed)

	@commands.slash_command()
	async def meta(self, inter: disnake.CmdInter, count: commands.Range[int, 1, 120] = 10): 
		"""Prints the top meta heroes from https://opendota.com/heroes
		
		Parameters
		----------
		count: The number of heroes to show
		"""
		await self.safe_defer(inter)
		json = await self.get_meta_json()
		sorted_json = self.sort_meta(json, count)
		description = (f"Top {count} meta hero(s) in professional matches")
		embed = disnake.Embed(description = description, color=self.embed_color)
		meta_table = disnake.File(await drawdota.draw_meta_table(sorted_json, json), "meta.png")
		embed.set_image(url=f"attachment://{meta_table.filename}")
		await inter.send(embed=embed, file=meta_table)

	@commands.slash_command()
	async def profile(self, inter: disnake.CmdInter, player: DotaPlayer = None):
		"""Displays information about the player's dota profile

		Parameters
		----------
		player: Either a steam32 id, a steam64 id, or an @mention of a discord user who has a steamid set
		"""
		if not player:
			player = await DotaPlayer.from_author(inter)
		steam32 = player.steam_id

		await self.safe_defer(inter)

		playerinfo = await opendota_query(f"/players/{steam32}")
		matches = await opendota_query(f"/players/{steam32}/matches")
		matches = list(filter(lambda m: m.get('player_slot') is not None, matches))

		rank_string = self.get_player_rank(playerinfo)

		gamesplayed = len(matches)
		if gamesplayed > 0:
			winrate = "{:.2%}".format(len(list(filter(lambda m: m.get('radiant_win', False) == ((m.get('player_slot', 0) or 0) < 128), matches))) / gamesplayed)
		else:
			winrate = "0%"

		heroes = {}
		for match in matches:
			heroes[match['hero_id']] = heroes.get(match['hero_id'], 0) + 1
		heroes = sorted(heroes.items(), key=lambda x: x[1], reverse=True)
		favs = ""
		for i in range(0,3):
			if i < len(heroes):
				favs += self.get_hero_info(heroes[i][0])['emoji']

		# Recent means 2 months / 60 days 
		timecutoff = time.time() - (86400 * 60)

		heroes = {}
		for match in matches:
			if match['start_time'] > timecutoff:
				heroes[match['hero_id']] = heroes.get(match['hero_id'], 0) + 1
		heroes = sorted(heroes.items(), key=lambda x: x[1], reverse=True)
		recent_favs = ""
		for i in range(0,3):
			if i < len(heroes):
				recent_favs += self.get_hero_info(heroes[i][0])['emoji']

		recent_count = 0
		activity_delta = []
		activity_count = []
		count = 1
		for i in range(0, len(matches) - 1):
			delta = matches[i]["start_time"] - (matches[i + 1]["start_time"] + matches[i]["duration"])
			if delta < (60 * 60 * 2): # If these are part of the same group
				count += 1
				continue
			else:
				activity_count.append(count)
				activity_delta.append(delta)
				count = 1
				if matches[i]["start_time"] > timecutoff:
					recent_count += 1

		if not activity_delta:
			activity_delta = [ 0 ]
			activity_count = [ 0 ]

		overall_time_played = 0
		for match in matches:
			overall_time_played += match["duration"]

		overall_activity_delta = get_pretty_time((int(statistics.mean(activity_delta)) // 60) * 60)
		if recent_count:
			recent_activity_delta = get_pretty_time((int(statistics.mean(activity_delta[:recent_count])) // 60) * 60)
		else:
			recent_activity_delta = None
		# overall_activity_count = int(statistics.mean(activity_count))
		# recent_activity_count = int(statistics.mean(activity_count[:recent_count]))

		plus_text = ""
		if playerinfo["profile"].get("plus"):
			plus_text = f"\n{self.get_emoji('dota_plus')} has Dota Plus"

		embed = disnake.Embed(color=self.embed_color)

		embed.set_author(
			name=playerinfo["profile"]["personaname"] or "Anonymous", 
			icon_url=playerinfo["profile"]["avatar"] or default_steam_icon, 
			url=playerinfo["profile"]["profileurl"] or f"https://www.opendota.com/players/{steam32}")

		embed.add_field(name="General", value=(
			f"Winrate: **{winrate}**\n"
			f"Games Played: **{gamesplayed}**\n"
			f"Total Hours In Game: **{overall_time_played // 3600:,}**\n"
			f"{rank_string}"
			f"{plus_text}"))

		embed.add_field(name="Profiles", value=(
			f"[Steam]({playerinfo['profile']['profileurl']})\n"
			f"[OpenDota](https://www.opendota.com/players/{steam32})\n"
			f"[DotaBuff](https://www.dotabuff.com/players/{steam32})\n"
			f"[STRATZ](https://www.stratz.com/player/{steam32})"))

		embed.add_field(name="Heroes", value=(
			f"[Recent Favs](https://www.opendota.com/players/{steam32}/heroes?date=60) {recent_favs}\n"
			f"[Overall Favs](https://www.opendota.com/players/{steam32}/heroes) {favs}\n"))

		embed.add_field(name="Activity", value=(
			"*Average time between groups of games*\n"
			f"**Recent**: {recent_activity_delta}\n"
			f"**Overall**: {overall_activity_delta}\n"), inline=False)

		
		if player.is_author:
			player_mention = ""
		else:
			player_mention = player.steam_id

		rank_icon = await drawdota.dota_rank_icon(playerinfo.get("rank_tier"), playerinfo.get("leaderboard_rank"))
		rank_icon = disnake.File(rank_icon, "rank.png")
		embed.set_thumbnail(url=f"attachment://{rank_icon.filename}")

		embed.set_footer(text=f"Steam ID: {steam32}")

		await inter.send(embed=embed, file=rank_icon)

	@commands.slash_command()
	async def twenty(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Gets stats from the player's last 20 parsed games

		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'
		"""
		matchfilter = await MatchFilter.init(matchfilter, inter)
		matchfilter.set_arg("limit", 20, True)
		matchfilter.set_arg("_parsed", True)

		await self.do_playerstats(inter, matchfilter, do_downloaded=True)

	@commands.slash_command()
	async def playerstats(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Gets stats about the player's dota matches

		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'
		"""
		matchfilter = await MatchFilter.init(matchfilter, inter)

		await self.do_playerstats(inter, matchfilter)

	# the main internal logic for the playerstats and twenty commands
	async def do_playerstats(self, inter: disnake.CmdInter, matchfilter: MatchFilter, do_downloaded=False):
		matchfilter.add_projections([ "kills", "deaths", "assists", "party_size", "version", "hero_id", "lane_role", "is_roaming", "lobby_type", "start_time", "duration" ])
		steam32 = matchfilter.player.steam_id

		await self.safe_defer(inter)
		# 
		# STEP 1: download all match data
		# 
		playerinfo = await opendota_query(f"/players/{steam32}")
		matches_info = await opendota_query_filter(matchfilter)
		matches_info = sorted(matches_info, key=lambda m: m["start_time"])
		player_matches = []

		if do_downloaded:
			matches = []
			i = 0
			while i < len(matches_info) and len(matches) < 20:
				if matches_info[i].get('version', None) is not None:
					match_id = matches_info[i]['match_id']
					match = await get_match(match_id)
					match["match_id"] = match_id
					player_match = next((p for p in match['players'] if p.get('account_id') == steam32), None)
					if player_match is not None:
						player_match["match_id"] = match_id
						player_matches.append(player_match)
						matches.append(match)
				i += 1
		else:
			player_matches = matches_info

		if len(player_matches) == 0:
			if do_downloaded:
				await inter.send("Not enough parsed matches!")
			else:
				await inter.send("Not enough matches found!")
			return

		# 
		# STEP 2: initialize discord embed, depending on what we filtered for
		# 
		embed = disnake.Embed(color=self.embed_color)
		embed_attachment = None

		embed.description = matchfilter.localize(matches_info) + "\n"
		embed.set_footer(text=f"To see the filtering options for this command, try \"/docs matchfilter\"")

		matches_url = f"https://www.opendota.com/players/{steam32}/matches?{matchfilter.to_query_args(for_web_url=True)}"
		author_name = playerinfo["profile"]["personaname"] or "Anonymous"
		author_icon_url = playerinfo["profile"]["avatar"] or default_steam_icon

		# if this is stats for playing as a specific hero
		if matchfilter.has_value("hero_id"):
			hero = self.lookup_hero(matchfilter.get_arg("hero_id"))
			if hero is not None:
				author_icon_url = self.get_hero_info(hero.id)["icon"]
				embed.set_thumbnail(url=self.get_hero_info(hero.id)['portrait'])
				embed.color = disnake.Color(int(hero.color[1:], 16))

		# if this is stats for playing with someone
		if matchfilter.has_value("included_account_id"):
			# make friends image
			avatar1 = playerinfo['profile']['avatarfull'] or default_steam_icon
			player2_id = matchfilter.get_arg("included_account_id")
			player2_info = await opendota_query(f"/players/{player2_id}")
			avatar2 = player2_info['profile']['avatarfull'] or default_steam_icon
			image = disnake.File(await drawdota.combine_image_halves(avatar1, avatar2), "profile.png")
			embed.set_thumbnail(url=f"attachment://{image.filename}")
			embed_attachment = image
			author_name += f" + {player2_info['profile']['personaname'] or 'Anonymous'}"

		# also add the dates of first and last match to description
		first_match = player_matches[0]
		last_match = player_matches[-1]
		def get_time_diff(match):
			timediff = time.time() - match["start_time"]
			timediff -= timediff % 60 # only show up to minutes level of detail
			if timediff > (29 * 60 * 60 * 24): # if was over a month ago
				timediff -= (timediff % (60 * 60 * 24)) # only show up to days level of detail
			if timediff > (3 * 60 * 60 * 24): # if was over a couple day ago
				timediff -= (timediff % (60 * 60)) # only show up to hours level of detail
			return get_pretty_time(timediff)
		embed.description += f"\n[First Match](https://www.opendota.com/matches/{first_match['match_id']}): {get_time_diff(first_match)} ago"
		embed.description += f"\n[Last Match](https://www.opendota.com/matches/{last_match['match_id']}): {get_time_diff(last_match)} ago"

		embed.set_author(
			name=author_name, 
			icon_url=author_icon_url, 
			url=matches_url)

		# 
		# STEP 3: define all stats together
		# 
		def avg(*args, **kwargs):
			return _match_avg(player_matches, *args, **kwargs)
		def percent(*args, **kwargs):
			return _match_percent(player_matches, *args, **kwargs)

		# compute favorites
		heroes = {}
		for match in player_matches:
			heroes[match['hero_id']] = heroes.get(match['hero_id'], 0) + 1
		heroes = sorted(heroes.items(), key=lambda x: x[1], reverse=True)
		favorite_heroes = "".join(map(lambda h: self.get_hero_info(h[0])['emoji'], heroes[0:3]))
		zeropercent = "0%"

		# laning postfix if needed
		laning_postfix = ""
		parsed_count = len(list(filter(lambda m: m.get("version") is not None, player_matches)))
		if parsed_count != len(player_matches) and not do_downloaded:
			laning_postfix = f" ({parsed_count} parsed matches)"

		class CoolStat():
			def __init__(self, caption, value, filter_key=None, ignore_value=None, separator=": ", bold=True):
				self.caption = caption
				self.value = value
				self.filter_key = filter_key
				self.ignore_value = ignore_value
				self.separator = separator
				self.bold = bold

			def should_show(self):
				return not(self.value == self.ignore_value or matchfilter.has_value(self.filter_key))

			def render(self):
				if not self.caption:
					return str(self.value)
				value = self.value
				if self.bold:
					value = f"**{value}**"
				return f"{self.caption}{self.separator}{value}"

		stat_sections = [
			{
				"caption": "General",
				"stats": [
					CoolStat(f"[Matches]({matches_url})", len(player_matches)),
					CoolStat("Winrate", percent(lambda p: p.get('radiant_win') == (p.get('player_slot') < 128)), filter_key="win"),
					CoolStat("KDA", f"{avg('kills')}/{avg('deaths')}/{avg('assists')}"),
					CoolStat("Duration", format_duration_simple(avg('duration') or 0)),
					CoolStat("In a Party", percent(lambda p: p.get('party_size') > 1, needs_key='party_size', round_place="floor")),
					CoolStat("Ranked", percent(lambda p: p['lobby_type'] == 7), filter_key="lobby_type")
				]
			},
			{
				"caption": "Heroes",
				"filter_key": "hero_id",
				"stats": [
					CoolStat(self.get_emoji('attr_strength'), percent(lambda p: self.get_hero_info(p['hero_id']).get('attr') == 'strength'), separator=" "),
					CoolStat(self.get_emoji('attr_agility'), percent(lambda p: self.get_hero_info(p['hero_id']).get('attr') == 'agility'), separator=" "),
					CoolStat(self.get_emoji('attr_intelligence'), percent(lambda p: self.get_hero_info(p['hero_id']).get('attr') == 'intelligence'), separator=" "),
					CoolStat(self.get_emoji('attr_universal'), percent(lambda p: self.get_hero_info(p['hero_id']).get('attr') == 'universal'), separator=" "),
					CoolStat("Randomed", percent('randomed'), ignore_value=zeropercent),
					CoolStat("__Favorites__", f"\n{favorite_heroes}")
				]
			},
			{
				"caption": f"Laning{laning_postfix}",
				"filter_key": "lane_role",
				"stats": [
					CoolStat("Safe Lane", percent(lambda p: p.get('lane_role') == 1 and not p.get('is_roaming'), needs_key="lane_role"), ignore_value=zeropercent),
					CoolStat("Mid Lane", percent(lambda p: p.get('lane_role') == 2 and not p.get('is_roaming'), needs_key="lane_role"), ignore_value=zeropercent),
					CoolStat("Off Lane", percent(lambda p: p.get('lane_role') == 3 and not p.get('is_roaming'), needs_key="lane_role"), ignore_value=zeropercent),
					CoolStat("Jungle", percent(lambda p: p.get('lane_role') == 4 and not p.get('is_roaming'), needs_key="lane_role"), ignore_value=zeropercent),
					CoolStat("Roaming", percent(lambda p: p.get('is_roaming'), needs_key="is_roaming"), ignore_value=zeropercent),
				]
			}
		]

		if do_downloaded:# if we've downloaded all of these matches, compute all the chat history stuff, and add the downloaded stats
			chat_wheel_counts = {}
			chat_wheel_total = 0
			longest_message_heading = "Longest Chat Message"
			message_count = 0
			longest_message = None
			longest_message_match_id = None
			for match in matches:
				player = next((p for p in match['players'] if p.get('account_id') == steam32), None)
				match_chat = match.get('chat', None)
				if match_chat:
					for message in match_chat:
						if message.get('player_slot', -1) == player['player_slot']:
							if message["type"] == "chat":
								message_count += 1
								if longest_message is None or len(longest_message) <= len(message['key']):
									longest_message = message['key']
									longest_message_match_id = match['match_id']
							elif message["type"] == "chatwheel":
								msg_id = int(message['key'])
								if msg_id >= 1000:
									continue # skip hero chat wheels
								chat_wheel_counts[msg_id] = chat_wheel_counts.get(msg_id, 0) + 1
								chat_wheel_total += 1

			message_count = int(round(message_count / len(matches)))
			if longest_message is not None:
				longest_message = f"\"{longest_message}\""
				longest_message_heading = f"[{longest_message_heading}](https://www.opendota.com/matches/{longest_message_match_id}/chat)"

			chat_wheel_text = "*No chat wheel usage found*"
			if chat_wheel_counts != {}:
				lines = []
				chat_wheel_counts = sorted(chat_wheel_counts.items(), key=lambda m: m[1], reverse=True)
				for i in range(0, min(3, len(chat_wheel_counts))):
					msg_id, count = chat_wheel_counts[i]
					message = self.chat_wheel_info.get(msg_id, { "message": "Unknown" })
					icon = self.get_emoji("chat_wheel_sound" if message.get('is_sound') else "chat_wheel_text")
					lines.append(f"{icon} {message['message']}")
				chat_wheel_text = "\n".join(lines)
			def wards_placed(p):
				obs = 0 if p.get('obs_placed') is None else p.get('obs_placed')
				sents = 0 if p.get('sen_placed') is None else p.get('sen_placed')
				return obs + sents

			# these are the downloaded_only sections
			stat_sections.extend([{
				"caption": "Economy",
				"stats": [
					CoolStat("GPM", avg('gold_per_min')),
					CoolStat("XPM", avg('xp_per_min')),
					CoolStat("Last Hits/min", avg(lambda p: p['last_hits'] / (1 + (p['duration'] / 60)), 2)),
					CoolStat("Neutral Creeps", avg(lambda p: 100 * p.get('neutral_kills', 0) / (1 + p['last_hits'])))
				]
			},
			{
				"caption": "Other",
				"stats": [
					CoolStat("APM", avg('actions_per_min')),
					CoolStat("Pings", avg('pings')),
					CoolStat("Wards Placed", avg(lambda p: wards_placed(p)))
				]
			},
			{
				"caption": "Chat Wheel",
				"stats": [ 
					CoolStat(None, chat_wheel_text)
				]
			},
			{
				"caption": "All Chat",
				"inline": False,
				"stats": [
					CoolStat("Messages per Game", message_count),
					CoolStat(longest_message_heading, longest_message, bold=False)
				]
			}])

		# 
		# STEP 4: transform these all into embed fields
		# 
		for category in stat_sections:
			if category.get("filter_key") and matchfilter.has_value(category.get("filter_key")):
				continue # skip this category if its already filtered out by the matchfilter
			value = "\n".join(map(lambda s: s.render(), filter(lambda s: s.should_show(), category.get("stats"))))
			if value == "":
				continue # skip if theres no values to show
			embed.add_field(name=category.get("caption"), value=value, inline=category.get("inline", True))

		if embed_attachment:
			await inter.send(embed=embed, file=image)
		else:
			await inter.send(embed=embed)

	@commands.slash_command()
	async def dotagif(self, inter: disnake.CmdInter, match: DotaMatch, start: str, end: str, ms_per_second : int = 100):
		"""Creates a gif of a specific part of a dota match
		

		Parameters
		----------
		match: The ID of the match, a reference to a player, or 'lm'. See '/docs Match Argument` for more info
		start: How many minutes into the match to start the gif. ex: 28:37
		end: How many minutes into the match to end the gif. ex: 30:30
		ms_per_second: How many miliseconds between each frame of the gif (each frame is 1 dota second)
		"""
		await self.safe_defer(inter)

		match = match.match
		match_id = match["match_id"]
		if not is_parsed(match):
			raise MatchNotParsedError(match_id, "get laning info")

		stratz_match = await get_stratz_match(match_id)
		if not is_stratz_parsed(stratz_match):
			raise StratzMatchNotParsedError(match_id)


		start = int(get_time(start))
		end = int(get_time(end))

		if end - start > 600:
			raise UserError("The length of this clip must be less than 10 minutes")

		if ms_per_second < 1 or ms_per_second > 655350:
			raise UserError("That is outside the bounds of the `ms_per_second` value")

		lastframe = match["duration"] - 1
		if start > lastframe and end > lastframe:
			raise UserError("The game didn't last that long")

		# "https://stratz.com/en-us/match/{match_id}/playback?pb_time={seconds}"

		image = disnake.File(await self.create_dota_gif(match, stratz_match, start, end, ms_per_second), "map.gif")
		await inter.send(file=image)


	@match.sub_command(name="laning")
	async def match_laning(self, inter: disnake.CmdInter, match: DotaMatch):
		"""Creates gif of the laning stage with a caption

		Parameters
		----------
		match: The ID of the match, a reference to a player, or 'lm'. See '/docs Match Argument` for more info
		"""
		steamid = match.steamid
		match = match.match
		match_id = match["match_id"]

		if not is_parsed(match):
			raise MatchNotParsedError(match_id, "get laning info")

		stratz_match = await get_stratz_match(match_id)
		if not is_stratz_parsed(stratz_match):
			raise StratzMatchNotParsedError(match_id)

		player_data = None
		if steamid:
			player_data = next((p for p in match['players'] if p['account_id'] == steamid), None)
		perspective = player_data.get("isRadiant") if player_data else True

		embed = disnake.Embed(description=await self.get_lane_stories(match, perspective, True))

		embed.title = f"Laning"
		embed.url = f"https://stratz.com/en-us/match/{match_id}/playback"

		image = disnake.File(await self.create_dota_gif(match, stratz_match, -89, 600, 100), "map.gif")
		embed.set_image(url=f"attachment://{image.filename}")

		self.set_match_footer(match, embed)

		await inter.send(embed=embed, file=image)


	@commands.slash_command()
	async def parse(self, inter: disnake.CmdInter, match_id: int = None):
		"""Request for OpenDota to parse a recent match
		
		Parameters
		----------
		match_id: The id of the match to parse. Leave this blank to parse your last played match
		"""
		if match_id is None:		
			matchfilter = await MatchFilter.convert(inter, "")
			if matchfilter.player:
				steamid = matchfilter.player.steam_id
			match_id = await get_lastmatch_id(matchfilter)

		await self.safe_defer(inter)

		try:
			data = await httpgetter.post(f"https://api.opendota.com/api/request/{match_id}", errors=opendota_html_errors)
		except HttpError as e:
			if e.code == 400:
				await inter.send("❌ Looks like that's not a valid match id")
				return
			raise

		if data.get("status") == "failed" or data.get("err") is not None:
			await inter.send(f"❌ There was an error requesting the parse for match {match_id}")
			return

		jobId = data["job"]["jobId"]
		await asyncio.sleep(3)
		seconds_per_check = 20
		seconds_till_timeout = 120

		while seconds_till_timeout > 0:
			data = await opendota_query(f"/request/{jobId}", False)

			if data is not None:
				await asyncio.sleep(seconds_per_check)
				seconds_till_timeout -= seconds_per_check
			else:
				await inter.send(f"✅ Parsing of match {match_id} has completed!")
				return

		# if we get to here, timeout
		await inter.send(f"❌ Parsing of match {match_id} timed out. Try again later or on the opendota site.", delete_after=10)


	@commands.slash_command()
	async def whoishere(self, inter: disnake.CmdInter, users: str = None, show_ranks: bool = False):
		"""Shows the linked steam accounts of anyone who is in voice chat with mango
		
		Parameters
		----------
		users: Any additional users to show the linked accounts of
		show_ranks: Whether or not to show the ranks of the players when showing their steam accounts
		"""
		if inter.guild is None:
			raise UserError("You have to use that command in a server")

		logger.info(users)

		additional_user_ids = []
		if users:
			matches = re.findall(r"<@!?(\d+)>", users)
			for match in matches:
				additional_user_ids.append(int(match))

		voice_channel = None
		if inter.author.voice and inter.author.voice.channel:
			voice_channel = inter.author.voice.channel
		else:
			audio = self.bot.get_cog("Audio")
			audioplayer = await audio.audioplayer(inter, False)
			if audioplayer is None or audioplayer.voice_channel is None:
				if len(additional_user_ids) == 0:
					raise UserError("One of us needs to be in a voice channel for that to work")
			else:
				voice_channel = audioplayer.voice_channel

		members = []
		if voice_channel:
			members.extend(map(lambda u: u.id, voice_channel.members))
		if additional_user_ids:
			members.extend(additional_user_ids)

		mentions = []
		links = []
		ranks = []

		for user_id in members:
			if voice_channel:
				if user_id == voice_channel.guild.me.id:
					continue
			mentions.append(f"<@!{user_id}>")
			userinfo = botdata.userinfo(user_id)
			if userinfo.steam is None:
				links.append("Unknown")
				ranks.append("Unknown")
			else:
				player_info = await opendota_query(f"/players/{userinfo.steam}")
				links.append(f"[{player_info['profile']['personaname']}](https://www.opendota.com/players/{userinfo.steam})")
				ranks.append(self.get_player_rank(player_info))


		if len(mentions) == 0:
			raise UserError("There isn't anyone in my voice channel 😢")
		#raise UserError("This command is broken right now but my developer is working on fixing it! For now you can mention people manually in the command and it should work.")

		embed = disnake.Embed()
		embed.add_field(name="Discord", value="\n".join(mentions))
		embed.add_field(name="Steam", value="\n".join(links))
		if show_ranks:
			embed.add_field(name="Rank", value="\n".join(ranks))

		await inter.send(embed=embed)

	@commands.slash_command()
	async def rolesgraph(self, inter: disnake.CmdInter, player: DotaPlayer = None):
		"""Gets a graph displaying the dota player's hero roles

		Parameters
		----------
		player: Either a steam32 id, a steam64 id, or an @mention of a discord user who has a steamid set
		"""
		await self.safe_defer(inter)
		if not player:
			player = await DotaPlayer.from_author(inter)

		playerinfo = await opendota_query(f"/players/{player.steam_id}")
		matches = await opendota_query(f"/players/{player.steam_id}/matches?limit=30")

		if len(matches) == 0:
			raise UserError("You haven't played any matches recently")

		hero_ids = []
		for match in matches:
			hero_ids.append(match["hero_id"])
		roles = [ "Escape", "Nuker", "Support", "Pusher", "Disabler", "Jungler", "Carry", "Durable", "Initiator" ]
		role_scores = dict.fromkeys(roles, 0)

		dotabase = self.bot.get_cog("Dotabase")
		for heroid in hero_ids:
			hero_info = self.get_hero_info(heroid)
			for role, value in hero_info["roles"].items():
				role_scores[role] += value

		role_scores = [role_scores[role] for role in roles]

		# weight it against the biases in the system
		role_totals = dict.fromkeys(roles, 0)
		for hero_info in self.hero_info.values():
			for role, value in hero_info["roles"].items():
				role_totals[role] += value
		role_totals = role_totals.values()
		role_totals_avg = sum(role_totals) / len(role_totals)
		role_totals_modifiers = list(map(lambda x: role_totals_avg / (x or 1), role_totals))
		for i in range(len(roles)):
			role_scores[i] *= role_totals_modifiers[i]

		# normalize so its a percentage based on the highest one
		divisor = max(role_scores)
		role_scores = list(map(lambda x: x / divisor, role_scores))

		embed = disnake.Embed()
		embed.set_author(
			name=playerinfo["profile"]["personaname"] or "Anonymous", 
			icon_url=playerinfo["profile"]["avatar"] or default_steam_icon, 
			url=playerinfo["profile"]["profileurl"] or f"https://www.opendota.com/players/{player.steam_id}")

		image = disnake.File(drawdota.draw_polygraph(role_scores, roles), "rolesgraph.png")
		embed.set_image(url=f"attachment://{image.filename}")
		await inter.send(embed=embed, file=image)

	@match.sub_command(name="skillbuild")
	async def match_skillbuild(self, inter: disnake.CmdInter, match: DotaMatch):
		"""Gets the ability upgrades for a match

		Parameters
		----------
		match: The ID of the match, a reference to a player, or 'lm'. See '/docs Match Argument` for more info
		"""
		match = match.match
		match_id = match["match_id"]

		embed = disnake.Embed()

		embed.title = f"Match {match_id}"
		embed.url = f"https://opendota.com/matches/{match_id}"

		embed.description = "Skill Builds"

		image = disnake.File(await drawdota.draw_match_ability_upgrades(match), "upgrades.png")
		embed.set_image(url=f"attachment://{image.filename}")

		self.set_match_footer(match, embed)

		await inter.send(embed=embed, file=image)

	@match.sub_command(name="graph")
	async def match_graph(self, inter: disnake.CmdInter, match: DotaMatch, graphtype: commands.option_enum(OrderedDict(graphtypes)) = "teamdiff"):
		"""Creates a graph for a dota match

		Parameters
		----------
		match: The ID of the match, a reference to a player, or 'lm'. See '/docs Match Argument` for more info
		graphtype: The type of graph to create
		"""
		match = match.match
		match_id = match["match_id"]

		if not is_parsed(match):
			raise MatchNotParsedError(match["match_id"], "create a graph")

		embed = disnake.Embed()

		embed.title = f"Match {match_id}"
		embed.url = f"https://opendota.com/matches/{match_id}"

		embed.description = next(key for key, value in graphtypes.items() if value == graphtype)

		if graphtype == "teamdiff":
			lines = [ match["radiant_gold_adv"], match["radiant_xp_adv"] ]
			colors = [ "#FFFF00", "#ADD8E6" ]
			labels = [ "Gold", "Experience" ]
		elif graphtype == "playergold":
			playercolors = {
				"0": "#3375FF",
				"1": "#66FFBF",
				"2": "#BF00BF",
				"3": "#F3F00B",
				"4": "#FF6B00",
				"128": "#FE86C2",
				"129": "#A1B447",
				"130": "#65D9F7",
				"131": "#008321",
				"132": "#A46900"
			}
			lines = []
			colors = []
			labels = []
			for player in match["players"]:
				colors.append(playercolors[str(player["player_slot"])] if str(player["player_slot"]) else "#FF0000")
				lines.append(player["gold_t"])
				labels.append(self.get_hero_info(player["hero_id"])["name"])
		else:
			raise UserError("oops, look like thats not implemented yet")

		image = disnake.File(drawgraph.drawgraph(lines, colors, labels), "graph.png")
		embed.set_image(url=f"attachment://{image.filename}")

		self.set_match_footer(match, embed)

		await inter.send(embed=embed, file=image)



	# @commands.command(aliases=["wrapped"])
	async def dotawrapped(self, ctx, player : DotaPlayer = None):
		"""Gets the "dota wrapped" summary for the player

		This is from the site https://gameishard.gg/dotawrapped/

		Yes, I got permission from the guy who made this to include this in mangobyte"""
		if not player:
			player = await DotaPlayer.from_author(ctx)

		wrapped_url = f"https://gameishard.gg/dotawrapped/?id={player.steam_id}"
		wrapped_image_url = f"https://gameishard.gg/dotawrapped/assets/images/players/{player.steam_id}.png"

		# await thinker.think(ctx.message)
		await httpgetter.get(wrapped_url, return_type="text")
		# await thinker.stop_thinking(ctx.message)

		embed = disnake.Embed()

		embed.title = f"Dota 2 Wrapped"
		embed.url = wrapped_url
		embed.set_image(url=wrapped_image_url)

		await ctx.send(embed=embed)

	@commands.slash_command()
	async def inventory(self, inter: disnake.CmdInter, matchfilter: MatchFilter = None):
		"""Shows the most commonly bought items for each slot in your inventory

		Parameters
		----------
		matchfilter: Specify how to filter these matches. To learn more, try '/docs Match Filter'
		"""
		matchfilter = await MatchFilter.init(matchfilter, inter)
		await self.safe_defer(inter)

		item_slots = [ "item_0", "item_1", "item_2", "item_3", "item_4", "item_5" ]
		matchfilter.add_projections(item_slots)

		matches = await opendota_query_filter(matchfilter)

		slot_item_counts = []
		for slot in item_slots:
			slot_item_counts.append({})
		for match in matches:
			for i in range(len(item_slots)):
				item = match.get(item_slots[i])
				if item is None or item == 0:
					continue
				if item not in slot_item_counts[i]:
					slot_item_counts[i][item] = 0
				slot_item_counts[i][item] += 1

		slot_item_counts = list(map(lambda item_counts: sorted(item_counts.items(), key=lambda x: x[1], reverse=True), slot_item_counts))

		# filter out duplicates (keep an item only in its best slot)
		items_best_slots = {} # key: item_id, value: (slot, count)
		for slot in range(len(slot_item_counts)):
			for item, count in slot_item_counts[slot]:
				if (item not in items_best_slots) or (items_best_slots[item][1] < count):
					items_best_slots[item] = (slot, count)
		for item, slot_count in items_best_slots.items():
			slot = slot_count[0]
			for i in range(len(slot_item_counts)):
				if i != slot:
					slot_item_counts[i] = list(filter(lambda item_count: item_count[0] != item, slot_item_counts[i]))

		embed = disnake.Embed()
		
		embed.title = "Common Items"
		embed.url = f"https://www.opendota.com/players/{matchfilter.player.steam_id}/matches"
		query_args = matchfilter.to_query_args()
		if query_args:
			embed.url += "?" + query_args
		
		embed.description = matchfilter.localize()
		embed.set_footer(text="The 3 most common items for each inventory slot. (At the end of the game)")

		image = disnake.File(await drawdota.draw_item_slots(slot_item_counts), "items.png")
		embed.set_image(url=f"attachment://{image.filename}")

		await inter.send(embed=embed, file=image)
				
	@commands.slash_command()
	async def percent(self, inter: disnake.CmdInter, filter1: MatchFilter = None, filter2: MatchFilter = None):
		"""Out of the matches that match filter1, the percent of them that also match filter2
    
		Parameters
		----------
		filter1: The primary filter that determines the denominator
		filter2: The secondary filter that determines the numerator
		"""
		await self.safe_defer(inter)

		filter1 = await MatchFilter.init(filter1, inter)
		filter2 = await MatchFilter.init(filter2, inter)
		
		matches1 = await opendota_query_filter(filter1)
		if not matches1:
			raise MatchNotFoundError(filter1)

		matches2 = await opendota_query_filter(filter2)

		matchids1 = list(map(lambda m: m["match_id"], matches1))
		matchids2 = list(map(lambda m: m["match_id"], matches2))
		both_matching = list(filter(lambda id: id in matchids2, matchids1))

		percent = 100 * len(both_matching) / len(matchids1)

		embed = disnake.Embed()

		embed.title = f"Percent: {percent:.2f}%"

		description = f"{len(both_matching)} out of {len(matchids1)} matches, or {percent:.2f}% is the answer to the question:\n\n"

		players_match = filter1.player.mention == filter2.player.mention

		filter1 = filter1.localize()
		filter2 = filter2.localize().replace("All matches ", "")
		filter2 = re.sub(r"^All matches", "", filter2)
		if players_match:
			filter2 = re.sub(r"^played by [^\s]+", "played", filter2)

		description += "**Out of** " + filter1 + ", **what percent of them were** " + filter2 + "?"

		embed.description = description

		await inter.send(embed=embed)



def setup(bot):
	bot.add_cog(DotaStats(bot))
