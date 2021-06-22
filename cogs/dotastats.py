from cogs.utils.metastats import get_total_pro_games
import discord
from discord.ext import commands
from __main__ import settings, botdata, thinker, httpgetter
from cogs.utils import checks
from cogs.utils.helpers import *
from cogs.utils.commandargs import *
from cogs.utils import drawdota
from cogs.utils import drawgraph
import asyncio
import async_timeout
import string
import datetime
import json
import re
import os
import urllib
import functools
import time
import statistics
import random
import aiohttp
import typing
import math
from types import *
from .mangocog import *

class MatchNotParsedError(UserError):
	def __init__(self, match_id, action=None):
		self.action = action if action else "do that"
		super().__init__(f"This match must be parsed before I can {self.action}.\nTry `{{cmdpfx}}parse {match_id}` to request a parse.")

class StratzMatchNotParsedError(UserError):
	def __init__(self, match_id):
		super().__init__(f"It looks like match `{match_id}` hasn't been parsed by STRATZ. To have your matches parsed by STRATZ a bit faster, you can login to their site: <https://stratz.com>")

class InvalidMatchIdError(UserError):
	def __init__(self, match_id):
		super().__init__(f"Sorry, looks like `{match_id}` isn't a valid match id")

opendota_html_errors = {
	404: "Dats not a valid query. Take a look at the OpenDota API Documentation: https://docs.opendota.com",
	521: "[http error 521] Looks like the OpenDota API is down or somethin, so ya gotta wait a sec",
	502: "[http error 502] Looks like there was an issue with the OpenDota API. Try again in a bit",
	"default": "OpenDota said we did things wrong 😢. http status code: {}"
}

default_steam_icon = "https://steamcdn-a.akamaihd.net/steamcommunity/public/images/avatars/fe/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"

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
	cached_data = httpgetter.cache.get(url, "json")

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
	url = f"https://api.stratz.com/api/v1/match/{match_id}"
	cached_data = httpgetter.cache.get(url, "json")
	
	if cached_data:
		if is_stratz_parsed(cached_data):
			return cached_data
		else:
			await httpgetter.cache.remove(url)

	try:
		return await httpgetter.get(url, cache=True, errors={
			500: "Looks like something wrong with the STRATZ api",
			204: "STRATZ hasn't recieved this match yet. Try again a bit later"
		})
	except aiohttp.ClientConnectorError:
		print("ClientConnectorError on stratz api result")
		raise StratzMatchNotParsedError(match_id)

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
			raise UserError("No matches found using that filter")


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
		self.embed_color = discord.Color.teal()
		dotabase = self.bot.get_cog("Dotabase")
		if not dotabase:
			raise ImportError("The Dotabase cog must be added before the DotaStats cog")
		self.dota_game_strings = read_json(settings.resource("json/dota_game_strings.json"))
		self.hero_info = dotabase.get_hero_infos()
		self.lookup_hero = dotabase.lookup_hero
		self.chat_wheel_info = dotabase.get_chat_wheel_infos()
		self.dota_gif_lock = asyncio.Lock()

	async def get_meta_json(self): 
		url = 'https://api.opendota.com/api/herostats'
		return await httpgetter.get(url)

	def sort_meta(self, json, num=10): 
		"""re-orders the meta json based on pick/ban + winrate.
		num = number of top heroes to include """
		total_games = get_total_pro_games(json)
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

	async def print_meta(self, ctx, num_to_list): 
		"""prints the meta table"""
		json = await self.get_meta_json()
		sorted_json = self.sort_meta(json, num_to_list)
		description = (f"Top {num_to_list} meta hero(s) in professional matches")
		embed = discord.Embed(description = description, color=self.embed_color)
		meta_table = discord.File(await drawdota.draw_meta_table(sorted_json, json), "meta.png")
		embed.set_image(url=f"attachment://{meta_table.filename}")
		await ctx.send(embed=embed, file=meta_table)

	def get_pretty_hero(self, player, use_icons=False):
		dotabase = self.bot.get_cog("Dotabase")
		if player["hero_id"] not in self.hero_info:
			return "**Unknown**"
		name = self.hero_info[player["hero_id"]]["name"]
		if use_icons:
			emoji = self.hero_info[player["hero_id"]]["emoji"]
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

	async def get_player_mention(self, steamid, ctx):
		# expects that steamid is a valid int
		player = await DotaPlayer.convert(ctx, steamid)
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
		fb_victim_id = next(h for h in self.hero_info if self.hero_info[h]['full_name'] == fb_log['key'])
		fb_victim = next(p for p in game['players'] if p['hero_id'] == fb_victim_id)

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

	async def tell_match_story(self, game, is_radiant, ctx, perspective=None):
		if not is_parsed(game):
			raise MatchNotParsedError(game["match_id"], "create a story")

		if not perspective:
			perspective = "The Radiant" if is_radiant else "The Dire"
			end_perspective = perspective
		else:
			end_perspective = f"{perspective} and their friends"

		story = (f"*Told from the perspective of {perspective}*\n"
				f"To see a more extensive story, try the [story tab](https://www.opendota.com/matches/{game['match_id']}/story) on opendota\n\n")

		story += await self.get_firstblood_story(game, is_radiant)

		story += await self.get_lane_stories(game, is_radiant)

		teamfights = await self.get_teamfight_stories(game, is_radiant)

		game_ending_state = "won" if (is_radiant == game['radiant_win']) else "lost"
		story_end = f"\n{end_perspective} {game_ending_state} the game at { get_pretty_duration(game['duration']) }"

		i = 0
		while i < len(teamfights) and (len(story) + len(teamfights[i]) + len(story_end)) < 2000:
			story += f"\n\n{teamfights[i]}"
			i += 1

		embed = discord.Embed(description=story, color=self.embed_color)
		embed.title = f"Story of Match {game['match_id']}"
		embed.url = f"https://www.opendota.com/matches/{game['match_id']}/story"
		embed.set_footer(text=f"For more information, try {self.cmdpfx(ctx)}match {game['match_id']}")
		await ctx.send(embed=embed)


	# prints the stats for the given player's latest game
	async def player_match_stats(self, steamid, match_id, ctx):
		match = await get_match(match_id)

		# Finds the player in the game which has our matching steam32 id
		player = next((p for p in match['players'] if p['account_id'] == steamid), None)
		if player is None:
			await self.print_match_stats(ctx, match_id)
			return

		dotabase = self.bot.get_cog("Dotabase")
		hero_name = self.hero_info[player['hero_id']]['name']

		duration = get_pretty_duration(match['duration'], postfix=False)
		winstatus = "Won" if player["win"] != 0 else "Lost"
		game_mode = self.dota_game_strings.get(f"game_mode_{match.get('game_mode')}", "Unknown")
		lobby_type = self.dota_game_strings.get(f"lobby_type_{match.get('lobby_type')}", "Unknown") + " "
		if lobby_type == "Normal ":
			lobby_type = ""

		description = (f"{winstatus} a {lobby_type}**{game_mode}** match as {hero_name} in {duration}. "
					f"More info at [DotaBuff](https://www.dotabuff.com/matches/{match_id}), "
					f"[OpenDota](https://www.opendota.com/matches/{match_id}), or "
					f"[STRATZ](https://www.stratz.com/match/{match_id})")

		embed = discord.Embed(description=description, color=self.embed_color, timestamp=datetime.datetime.utcfromtimestamp(match['start_time']))

		embed.set_author(name=player.get('personaname') or "Anonymous", icon_url=self.hero_info[player['hero_id']]['icon'], url="https://www.opendota.com/players/{}".format(steamid))

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

		match_image = discord.File(await drawdota.create_match_image(match), "match.png")
		embed.set_image(url=f"attachment://{match_image.filename}")
		embed.set_footer(text=str(match_id))

		await ctx.send(embed=embed, file=match_image)

	@commands.command(aliases=["lastgame", "lm"])
	async def lastmatch(self, ctx, *, matchfilter : MatchFilter = None):
		"""Gets info about the player's last dota game

		To see how to filter for specific matches, try `{cmdpfx}docs matchfilter`"""
		await ctx.channel.trigger_typing()
		
		matchfilter = await MatchFilter.init(matchfilter, ctx)
		player = matchfilter.player

		match_id = await get_lastmatch_id(matchfilter)
		await self.player_match_stats(player.steam_id, match_id, ctx)

	@commands.command(aliases=["firstgame", "fm"])
	async def firstmatch(self, ctx, *, matchfilter : MatchFilter = None):
		"""Gets info about the player's first dota game

		To see how to filter for specific matches, try `{cmdpfx}docs matchfilter`"""
		await ctx.channel.trigger_typing()
		
		matchfilter = await MatchFilter.init(matchfilter, ctx)
		player = matchfilter.player

		match_id = await get_lastmatch_id(matchfilter, reverse=True)
		await self.player_match_stats(player.steam_id, match_id, ctx)

	async def print_match_stats(self, ctx, match_id):
		match = await get_match(match_id)
		duration = get_pretty_duration(match['duration'], postfix=False)
		game_mode = self.dota_game_strings.get(f"game_mode_{match.get('game_mode')}", "Unknown")
		lobby_type = self.dota_game_strings.get(f"lobby_type_{match.get('lobby_type')}", "Unknown") + " "
		if lobby_type == "Normal ":
			lobby_type = ""

		description = (f"This {lobby_type}**{game_mode}** match ended in {duration} \n"
					f"More info at [DotaBuff](https://www.dotabuff.com/matches/{match_id}), "
					f"[OpenDota](https://www.opendota.com/matches/{match_id}), or "
					f"[STRATZ](https://www.stratz.com/match/{match_id})")

		embed = discord.Embed(description=description, 
							timestamp=datetime.datetime.utcfromtimestamp(match['start_time']), color=self.embed_color)
		embed.set_author(name="Match {}".format(match_id), url="https://www.opendota.com/matches/{}".format(match_id))

		embed.add_field(name="Game Mode", value=game_mode)
		embed.add_field(name="Lobby Type", value=game_mode)

		match_image = discord.File(await drawdota.create_match_image(match), filename="matchimage.png")

		embed.set_image(url=f"attachment://{match_image.filename}")
		embed.set_footer(text=str(match_id))
		await ctx.send(embed=embed, file=match_image)


	@commands.command(aliases=["matchdetails"])
	async def match(self, ctx, match_id : int):
		"""Gets a summary of the dota match with the given id"""
		await ctx.channel.trigger_typing()
		await self.print_match_stats(ctx, match_id)


	@commands.command()
	async def matchstory(self, ctx, match_id : int, perspective=None):
		"""Tells the story of the match

		The story is based on the given perspective, or the player's perspective if they were in the match."""
		await ctx.channel.trigger_typing()

		steamid = None
		try:
			player = await DotaPlayer.from_author(ctx)
			steamid = player.steam_id
		except Exception as e:
			pass

		match = await get_match(match_id)

		if perspective is None:
			player_data = next((p for p in match['players'] if p['account_id'] == steamid), None)
			if steamid is not None and player_data is not None:
				is_radiant = player_data['isRadiant']
				perspective = "{2}({0}, {1})".format(self.get_pretty_hero(player_data), "Radiant" if is_radiant else "Dire", ctx.message.author.mention)
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
		

		await self.tell_match_story(match, is_radiant, ctx, perspective)

	@commands.command(aliases=["lastgamestory", "lmstory"])
	async def lastmatchstory(self, ctx, player : DotaPlayer = None):
		"""Tells the story of the player's last match

		Input must be either a discord user, a steam32 id, or a steam64 id"""
		await ctx.channel.trigger_typing()
		if not player:
			player = await DotaPlayer.from_author(ctx)

		perspective = player.mention
		try:
			match_id = (await opendota_query(f"/players/{player.steam_id}/matches?limit=1"))[0]['match_id']
			game = await get_match(match_id)
		except UserError:
			await ctx.send("I can't find the last game this player played")
			return
		if player is None:
			player = ctx.message.author.mention

		player_data = next((p for p in game['players'] if p['account_id'] == player.steam_id), None)
		perspective += "({0}, {1})".format(self.get_pretty_hero(player_data), "Radiant" if player_data['isRadiant'] else "Dire")

		await self.tell_match_story(game, player_data['isRadiant'], ctx, perspective)

	@commands.command(aliases=["recentmatches", "recent"])
	async def matches(self, ctx, *, matchfilter : MatchFilter = None):
		"""Gets a list of your matches

		The date/time is localized based off of the server that the game was played on, which means it may not match your timezone.

		To see how to filter for specific matches, try `{cmdpfx}docs matchfilter`

		Note that you can have this show up to 100 matches, but will by default only show 10, unless a timespan is given

		**Example:**
		`{cmdpfx}matches @PlayerPerson mid witch doctor ranked`
		`{cmdpfx}matches natures prophet`
		`{cmdpfx}matches @PlayerPerson riki`"""
		await ctx.channel.trigger_typing()

		matchfilter = await MatchFilter.init(matchfilter, ctx)

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
			raise UserError("I can't find any matches that match that filter")

		matches = sorted(matches, key=lambda m: m.get("start_time"), reverse=True)


		embed = discord.Embed()

		embed.title = "Recent Matches"
		embed.url = f"https://www.opendota.com/players/{steam32}/matches"
		if hero:
			embed.title += f" as {hero.localized_name}"
			embed.url += f"?hero_id={hero.id}"
			if hero.color:
				embed.color = discord.Color(int(hero.color[1:], 16))

		matches_image = await drawdota.draw_matches_table(matches, self.dota_game_strings)
		matches_image = discord.File(matches_image, "matches.png")
		embed.set_image(url=f"attachment://{matches_image.filename}")
		embed.set_footer(text=f"Try {self.cmdpfx(ctx)}matchids to get copy-pastable match ids")

		await ctx.send(embed=embed, file=matches_image)

	@commands.command()
	async def matchids(self, ctx, *, matchfilter : MatchFilter = None):
		"""Gets a list of matchids that match the given filter

		To see how to filter for specific matches, try `{cmdpfx}docs matchfilter`

		**Example:**
		`{cmdpfx}matchids @PlayerPerson mid witch doctor ranked`
		`{cmdpfx}matchids natures prophet`
		`{cmdpfx}matchids @PlayerPerson riki`"""
		await ctx.channel.trigger_typing()

		matchfilter = await MatchFilter.init(matchfilter, ctx)

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
			raise UserError("I can't find any matches that match that filter")

		matches = sorted(matches, key=lambda m: m.get("start_time"), reverse=True)


		embed = discord.Embed()

		embed.title = "Recent Matches"
		embed.url = f"https://www.opendota.com/players/{steam32}/matches"

		embed.description = "```\n"
		embed.description += "\n".join(list(map(lambda m: str(m["match_id"]), matches)))
		embed.description += "\n```"

		embed.set_footer(text=f"Try {self.cmdpfx(ctx)}matches to get more details about these matches")

		await ctx.send(embed=embed)

	@commands.command()
	async def meta(self, ctx, *, count : int = 10): 
		"""prints the top meta heroes from https://opendota.com/heroes"""
		await ctx.channel.trigger_typing()
		if count > 119:
			raise UserError("Limit of matches can't be more than the number of heroes")
		if count < 1: 
			raise UserError("Limit of matches can't be less than 1")
		await self.print_meta(ctx, count)

	@commands.command(aliases=["whois"])
	async def profile(self, ctx, player : DotaPlayer = None):
		"""Displays information about the player's dota profile

		The argument for this command can be either a steam32 id, a steam64 id, or an @mention of a discord user who has a steamid set"""
		if not player:
			player = await DotaPlayer.from_author(ctx)
		steam32 = player.steam_id

		await ctx.channel.trigger_typing()

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
				favs += self.hero_info[heroes[i][0]]['emoji']

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
				recent_favs += self.hero_info[heroes[i][0]]['emoji']

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

		embed = discord.Embed(color=self.embed_color)

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
		rank_icon = discord.File(rank_icon, "rank.png")
		embed.set_thumbnail(url=f"attachment://{rank_icon.filename}")

		embed.set_footer(text=f"Steam ID: {steam32}")

		await ctx.send(embed=embed, file=rank_icon)

	@commands.command(aliases=["chatstats"])
	async def twenty(self, ctx, *, matchfilter : MatchFilter = None):
		"""Gets stats from the player's last 20 parsed games

		Note that this only cares about **parsed** games, and unparsed games will be ignored. If the player has less than 20 parsed matches, we'll use all the parsed matches available

		To see how to filter for specific matches, try `{cmdpfx}docs matchfilter`"""
		matchfilter = await MatchFilter.init(matchfilter, ctx)
		matchfilter.set_arg("limit", 20, True)
		matchfilter.set_arg("_parsed", True)

		await self.do_playerstats(ctx, matchfilter, do_downloaded=True)

	@commands.command(aliases=["pstats", "herostats"])
	async def playerstats(self, ctx, *, matchfilter : MatchFilter = None):
		"""Gets player match statistics

		By default this will target all the matches a player has played.

		**Note:** If you're wondering why some data is now missing, check out `{cmdpfx}twenty`. I've revamped this command to work for all matches, and `{cmdpfx}twenty` is the old version of what this command used to be.
		
		To see how to filter for specific matches, try `{cmdpfx}docs matchfilter`"""
		matchfilter = await MatchFilter.init(matchfilter, ctx)

		await self.do_playerstats(ctx, matchfilter)

	# the main internal logic for the playerstats and twenty commands
	async def do_playerstats(self, ctx, matchfilter, do_downloaded=False):
		matchfilter.add_projections([ "kills", "deaths", "assists", "party_size", "version", "hero_id", "lane_role", "is_roaming", "lobby_type", "start_time", "duration" ])
		steam32 = matchfilter.player.steam_id

		# 
		# STEP 1: download all match data
		# 
		with ctx.channel.typing():
			await thinker.think(ctx.message)
			playerinfo = await opendota_query(f"/players/{steam32}")
			matches_info = await opendota_query_filter(matchfilter)
			matches_info = sorted(matches_info, key=lambda m: m["start_time"])
			player_matches = []

			if do_downloaded:
				matches = []
				i = 0
				while i < len(matches_info) and len(matches) < 20:
					if matches_info[i].get('version', None) is not None:
						match = await get_match(matches_info[i]['match_id'])
						player_match = next((p for p in match['players'] if p['account_id'] == steam32), None)
						if player_match is not None:
							player_matches.append(player_match)
							matches.append(match)
					i += 1
			else:
				player_matches = matches_info


		await thinker.stop_thinking(ctx.message)
		if len(player_matches) == 0:
			if do_downloaded:
				await ctx.send("Not enough parsed matches!")
			else:
				await ctx.send("Not enough matches found!")
			return

		# 
		# STEP 2: initialize discord embed, depending on what we filtered for
		# 
		embed = discord.Embed(color=self.embed_color)
		embed_attachment = None

		if do_downloaded:
			embed.description = f"*The following are averages and percentages based on the last {len(player_matches)} parsed matches*"
		else:
			embed.description = ""
		embed.set_footer(text=f"To see the filtering options for this command, try \"{self.cmdpfx(ctx)}docs matchfilter\"")

		matches_url = f"https://www.opendota.com/players/{steam32}/matches?{matchfilter.to_query_args(for_web_url=True)}"
		author_name = playerinfo["profile"]["personaname"] or "Anonymous"
		author_icon_url = playerinfo["profile"]["avatar"] or default_steam_icon

		# if this is stats for playing as a specific hero
		if matchfilter.has_value("hero_id"):
			hero = self.lookup_hero(matchfilter.get_arg("hero_id"))
			author_icon_url = self.hero_info[hero.id]["icon"]
			embed.set_thumbnail(url=self.hero_info[hero.id]['portrait'])
			embed.color = discord.Color(int(hero.color[1:], 16))

		# if this is stats for playing with someone
		if matchfilter.has_value("included_account_id"):
			# make friends image
			avatar1 = playerinfo['profile']['avatarfull'] or default_steam_icon
			player2_id = matchfilter.get_arg("included_account_id")
			player2_info = await opendota_query(f"/players/{player2_id}")
			avatar2 = player2_info['profile']['avatarfull'] or default_steam_icon
			image = discord.File(await drawdota.combine_image_halves(avatar1, avatar2), "profile.png")
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
		favorite_heroes = "".join(map(lambda h: self.hero_info[h[0]]['emoji'], heroes[0:3]))
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
					CoolStat(self.get_emoji('attr_strength'), percent(lambda p: self.hero_info.get(p['hero_id'], {}).get('attr') == 'strength'), separator=" "),
					CoolStat(self.get_emoji('attr_agility'), percent(lambda p: self.hero_info.get(p['hero_id'], {}).get('attr') == 'agility'), separator=" "),
					CoolStat(self.get_emoji('attr_intelligence'), percent(lambda p: self.hero_info.get(p['hero_id'], {}).get('attr') == 'intelligence'), separator=" "),
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
				player = next((p for p in match['players'] if p['account_id'] == steam32), None)
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
			await ctx.send(embed=embed, file=image)
		else:
			await ctx.send(embed=embed)

	@commands.command(aliases=["dota_gif"])
	async def dotagif(self, ctx, match_id : int, start, end, ms_per_second : int = 100):
		"""Creates a gif of a specific part of a dota match

		The part of the match that you specify must be less than 10 minutes long

		`ms_per_second` is how many miliseconds between frames of the gif (each frame is 1 dota second)

		**Example:**
		`{cmdpfx}dotagif 3370877768 28:37 30:30`"""
		await ctx.channel.trigger_typing()

		match = await get_match(match_id)
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

		async with ctx.channel.typing():
			await thinker.think(ctx.message)
			try:
				image = discord.File(await self.create_dota_gif(match, stratz_match, start, end, ms_per_second), "map.gif")
				await ctx.send(file=image)
			finally:
				await thinker.stop_thinking(ctx.message)

	@commands.command(aliases=["lanes"])
	async def laning(self, ctx, match_id : int = None):
		"""Creates gif of the laning stage with a caption

		If no match id is given and the user has a steam account connected, uses the player's most recently played match"""
		await ctx.channel.trigger_typing()
		try:
			player = await DotaPlayer.from_author(ctx)
			steamid = player.steam_id
		except CustomBadArgument:
			steamid = None
			pass
		if match_id is None:
			if steamid is None:
				raise SteamNotLinkedError()
			matchfilter = await MatchFilter.init(None, ctx)
			match_id = await get_lastmatch_id(matchfilter)
		

		match = await get_match(match_id)
		if not is_parsed(match):
			raise MatchNotParsedError(match_id, "get laning info")

		stratz_match = await get_stratz_match(match_id)
		if not is_stratz_parsed(stratz_match):
			raise StratzMatchNotParsedError(match_id)

		player_data = None
		if steamid:
			player_data = next((p for p in match['players'] if p['account_id'] == steamid), None)
		perspective = player_data.get("isRadiant") if player_data else True

		embed = discord.Embed(description=await self.get_lane_stories(match, perspective, True))

		embed.title = f"Laning"
		embed.url = f"https://stratz.com/en-us/match/{match_id}/playback"


		async with ctx.channel.typing():
			await thinker.think(ctx.message)
			try:
				image = discord.File(await self.create_dota_gif(match, stratz_match, -89, 600, 100), "map.gif")
				embed.set_image(url=f"attachment://{image.filename}")
				await ctx.send(embed=embed, file=image)
			finally:
				await thinker.stop_thinking(ctx.message)


	@commands.command(aliases=["analyze", "studymatch"])
	async def parse(self, ctx, match_id : int = None):
		"""Requests that OpenDota parses a match

		The input should be the match_id of the match

		Note that matches from more than a couple days ago may not be able to be parsed because replay files are not saved that long

		Not giving a matchid will make mangobyte attempt to use your last played match"""
		if match_id is None:		
			matchfilter = await MatchFilter.init(None, ctx)
			match_id = await get_lastmatch_id(matchfilter)

		await ctx.message.add_reaction("⏳")
		await ctx.send("⏳ Requesting a parse...", delete_after=5)

		try:
			data = await httpgetter.post(f"https://api.opendota.com/api/request/{match_id}", errors=opendota_html_errors)
		except HttpError as e:
			await ctx.message.remove_reaction("⏳", self.bot.user)
			if e.code == 400:
				await ctx.send("❌ Looks like that's not a valid match id")
				return
			raise

		if data.get("status") == "failed" or data.get("err") is not None:
			await ctx.message.remove_reaction("⏳", self.bot.user)
			await ctx.send(f"❌ There was an error requesting the parse for match {match_id}")
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
				await ctx.message.remove_reaction("⏳", self.bot.user)
				await ctx.message.add_reaction("✅")
				await ctx.send(f"✅ Parsing of match {match_id} has completed!", delete_after=10)
				return

		# if we get to here, timeout
		await ctx.message.remove_reaction("⏳", self.bot.user)
		await ctx.message.add_reaction("❌")
		await ctx.send(f"❌ Parsing of match {match_id} timed out. Try again later or on the opendota site.", delete_after=10)


	@commands.command(aliases=["profiles"])
	async def whoishere(self, ctx, *, mentions_or_rank = None):
		"""Shows what discord users are which steam users

		This command will take the users that are currently in the channel mangobyte is in, and create an embed that shows who they are in steam. If you are in a voice channel, it will use the channel that you are in

		You can also mention the users you want to show and it will show those ones too

		If you use the word `rank` somewhere in the command, it will also show the ranks of the players"""
		if ctx.message.guild is None:
			raise UserError("You have to use that command in a server")

		voice_channel = None
		if ctx.author.voice and ctx.author.voice.channel:
			voice_channel = ctx.author.voice.channel
		else:
			audio = self.bot.get_cog("Audio")
			audioplayer = await audio.audioplayer(ctx, False)
			if audioplayer is None or audioplayer.voice_channel is None:
				if len(ctx.message.mentions) == 0:
					raise UserError("One of us needs to be in a voice channel for that to work")
			else:
				voice_channel = audioplayer.voice_channel

		show_ranks = "rank" in (mentions_or_rank if mentions_or_rank else "")

		members = []
		if voice_channel:
			members.extend(voice_channel.members)
		if ctx.message.mentions:
			members.extend(ctx.message.mentions)

		mentions = []
		links = []
		ranks = []

		for member in members:
			if voice_channel:
				if member.id == voice_channel.guild.me.id:
					continue
			mentions.append(member.mention)
			userinfo = botdata.userinfo(member.id)
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

		embed = discord.Embed()
		embed.add_field(name="Discord", value="\n".join(mentions))
		embed.add_field(name="Steam", value="\n".join(links))
		if show_ranks:
			embed.add_field(name="Rank", value="\n".join(ranks))

		await ctx.send(embed=embed)

	@commands.command()
	async def opendota(self, ctx, *, query):
		"""Queries the opendota api

		You can use this to get a json file with details about players or matches etc.
		Examples:
		`{cmdpfx}opendota /players/{steamid}`
		`{cmdpfx}opendota /matches/{match_id}`

		Note that this is just a little tool showcasing how you can use the api. You can also put urls like these in your browser to get the same results, which I'd recommend if you're doing this a lot.

		For more options and a better explanation, check out their [documentation](https://docs.opendota.com)"""
		query = query.replace("/", " ")
		query = query.strip()
		query = "/" + "/".join(query.split(" "))
		query = re.sub("[^/0-9a-zA-Z?=&_]", "", query)

		with ctx.channel.typing():
			data = await opendota_query(query)

		tempdir = settings.resource("temp")
		if not os.path.exists(tempdir):
			os.makedirs(tempdir)
		filename = re.search("/([/0-9a-zA-Z]+)", query).group(1).replace("/", "_")
		filename = tempdir + f"/{filename}.json"
		write_json(filename, data)
		await ctx.send(file=discord.File(filename))
		os.remove(filename)

	@commands.command()
	async def rolesgraph(self, ctx, player : DotaPlayer = None):
		"""Gets a graph displaying the player's hero roles

		The graph is based on the player's last 30 games
		"""
		if not player:
			player = await DotaPlayer.from_author(ctx)

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
			hero_info = self.hero_info[heroid]
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
		role_totals_modifiers = list(map(lambda x: role_totals_avg / x, role_totals))
		for i in range(len(roles)):
			role_scores[i] *= role_totals_modifiers[i]

		# normalize so its a percentage based on the highest one
		divisor = max(role_scores)
		role_scores = list(map(lambda x: x / divisor, role_scores))

		embed = discord.Embed()
		embed.set_author(
			name=playerinfo["profile"]["personaname"] or "Anonymous", 
			icon_url=playerinfo["profile"]["avatar"] or default_steam_icon, 
			url=playerinfo["profile"]["profileurl"] or f"https://www.opendota.com/players/{player.steam_id}")

		image = discord.File(drawdota.draw_polygraph(role_scores, roles), "rolesgraph.png")
		embed.set_image(url=f"attachment://{image.filename}")
		await ctx.send(embed=embed, file=image)

	@commands.command(aliases=["abilitybuild", "skillbuilds", "matchbuilds"])
	async def skillbuild(self, ctx, match_id : int):
		"""Gets the ability upgrades for a match

		Shows all the ability upgrade orders for all heroes in the match"""
		match = await get_match(match_id)

		embed = discord.Embed()

		embed.title = f"Match {match_id}"
		embed.url = f"https://opendota.com/matches/{match_id}"

		async with ctx.channel.typing():
			image = discord.File(await drawdota.draw_match_ability_upgrades(match), "upgrades.png")
			embed.set_image(url=f"attachment://{image.filename}")
			await ctx.send(embed=embed, file=image)

	@commands.command(aliases=["graph", "dotagraph"])
	async def matchgraph(self, ctx, *, options = ""):
		"""Creates a graph for a dota match

		Give this match a match_id or it will try to use your last played game

		different types of graphs:
		teamdiff: creates a graph of the networth/xp differences between the teams
		playergold: creates a graph of the networths of the players throughout the match
		(ill probably add more in the futre but thats it for now)
		"""
		graphtypes = {
			"teamdiff": {
				"pattern": "(team)? ?(diff|networth)",
				"name": "Team Gold/Experience Difference"
			},
			"playergold": {
				"pattern": "(players? ?(gold)?)",
				"name": "Player Gold"
			}
		}

		graphtype = "teamdiff"

		for key in graphtypes:
			pattern = graphtypes[key]["pattern"]
			if re.match(pattern, options):
				options = re.sub(pattern, "", options)
				graphtype = key
				break

		options = options.strip()

		if options.isnumeric():
			match_id = int(options)
		elif options == "":
			try:
				player = await DotaPlayer.from_author(ctx)
				steamid = player.steam_id
			except CustomBadArgument:
				steamid = None
				raise SteamNotLinkedError()
			matchfilter = await MatchFilter.init(None, ctx)
			match_id = await get_lastmatch_id(matchfilter)
		else:
			raise UserError(f"I'm not sure what \"{options}\" means")

		match = await get_match(match_id)

		if not is_parsed(match):
			raise MatchNotParsedError(match["match_id"], "create a graph")

		embed = discord.Embed()

		embed.title = f"Match {match_id}"
		embed.url = f"https://opendota.com/matches/{match_id}"
		embed.set_footer(text=f"This is a rough draft, im planning on making this much better soon")

		embed.description = graphtypes[graphtype]["name"]

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
				labels.append(self.hero_info[player["hero_id"]]["name"] if player["hero_id"] in self.hero_info else "Unknown")
		else:
			raise UserError("oops, look like thats not implemented yet")

		async with ctx.channel.typing():
			image = discord.File(drawgraph.drawgraph(lines, colors, labels), "graph.png")
			embed.set_image(url=f"attachment://{image.filename}")
			await ctx.send(embed=embed, file=image)



	# @commands.command(aliases=["wrapped"])
	async def dotawrapped(self, ctx, player : DotaPlayer = None):
		"""Gets the "dota wrapped" summary for the player

		This is from the site https://gameishard.gg/dotawrapped/

		Yes, I got permission from the guy who made this to include this in mangobyte"""
		if not player:
			player = await DotaPlayer.from_author(ctx)

		wrapped_url = f"https://gameishard.gg/dotawrapped/?id={player.steam_id}"
		wrapped_image_url = f"https://gameishard.gg/dotawrapped/assets/images/players/{player.steam_id}.png"

		await thinker.think(ctx.message)
		await httpgetter.get(wrapped_url, return_type="text")
		await thinker.stop_thinking(ctx.message)

		embed = discord.Embed()

		embed.title = f"Dota 2 Wrapped"
		embed.url = wrapped_url
		embed.set_image(url=wrapped_image_url)

		await ctx.send(embed=embed)





def setup(bot):
	bot.add_cog(DotaStats(bot))
