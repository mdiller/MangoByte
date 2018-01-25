import discord
from discord.ext import commands
from __main__ import settings, botdata, thinker, httpgetter
from cogs.utils import checks
from cogs.utils.helpers import *
from cogs.utils import drawdota
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
from types import *
from .mangocog import *

class SteamNotLinkedError(UserError):
	def __init__(self, user=None):
		self.is_author = user is None
		self.user = user
		if not self.is_author:
			super().__init__(f"{user.name} doesn't have a steam account linked. They should try `?help setsteam` to see how to link their steam account.")
		else:
			super().__init__("Yer steam account isn't linked to yer discord account yet.\nTry doin `?help setsteam` to see how to link a steam account.")

class MatchNotParsedError(UserError):
	def __init__(self, match_id, action=None):
		self.action = action if action else "do that"
		super().__init__(f"This match must be parsed before I can {self.action}.\nTry `?parse {match_id}` to request a parse.")

class InvalidMatchIdError(UserError):
	def __init__(self, match_id):
		super().__init__(f"Sorry, looks like `{match_id}` isn't a valid match id")

opendota_html_errors = {
	404: "Dats not a valid query. Take a look at the OpenDota API Documentation: https://docs.opendota.com",
	521: "Looks like the OpenDota API is down or somethin, so ya gotta wait a sec",
	"default": "OpenDota said we did things wrong 😢. status code: {}"
}

async def opendota_query(querystring, cache=False):
	return await httpgetter.get(f"https://api.opendota.com/api{querystring}", cache=cache, errors=opendota_html_errors)

# rate_limit = false if this is the only query we're sending
async def get_match(match_id):
	url = f"https://api.opendota.com/api/matches/{match_id}"
	cached_data = httpgetter.cache.get(url, "json")
	
	if cached_data:
		if cached_data["version"]:
			return cached_data
		else:
			await httpgetter.cache.remove(url)

	try:
		return await opendota_query(f"/matches/{match_id}", cache=True)
	except HttpError as e:
		if e.code == 404:
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

	return await httpgetter.get(url, cache=True, errors={
		500: "Looks like something wrong with the STRATZ api"
	})

async def get_lastmatch_id(steamid):
	matches = await opendota_query(f"/players/{steamid}/recentmatches")
	if matches:
		return matches[0]["match_id"]
	else:
		raise UserError("Couldn't find any recent matches for you. Try enabling the \"Expose Public Match Data\" option in dota")

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
	return match.get("parsedDate") and match["players"][0].get("eventData") and match["players"][0].get("eventData").get("playerUpdatePositionEvents")

# gets the steam32 id from the user or steamid and checks that it is valid before returning
# If ref is specified, returns either a link or a discord user mention, depending on the input
async def get_check_steamid(player, ctx, mention=False, no_error=False):
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
		player_info = await opendota_query(f"/players/{player}")

		if player_info.get("profile") is None:
			raise UserError("Either this person doesn't play dota, or they haven't enabled public match data")
		if mention:
			return player, f"[{player_info['profile']['personaname']}](https://www.opendota.com/players/{player})"
		else:
			return player

	if not isinstance(player, discord.User):
		try:
			player = await commands.MemberConverter().convert(ctx, str(player))
		except commands.BadArgument:
			if no_error:
				return None
			raise UserError("Ya gotta @mention a user who has been linked to a steam id, or just give me a their steam id")

	userinfo = botdata.userinfo(player.id)
	if userinfo.steam32 is None:
		if no_error:
			return None
		if is_author:
			raise SteamNotLinkedError()
		else:
			raise SteamNotLinkedError(player)

	if mention:
		return userinfo.steam32, player.mention
	else:
		return userinfo.steam32


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




class DotaStats(MangoCog):
	"""Dota player and match stats

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

	def get_pretty_hero(self, player):
		dotabase = self.bot.get_cog("Dotabase")
		return "**{}**".format(self.hero_info[player['hero_id']]['name'])

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


	async def get_timeline_story(self, game, is_radiant):
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
		for line in timeline:
			story += "\n" + line['formatted'] + "\n"

		return story

	async def get_lane_story(self, players, laneid, is_radiant):
		our_eff = 0
		their_eff = 0
		our_heroes = []
		their_heroes = []
		for player in players:
			if player['lane'] == laneid and not player.get('is_roaming', False):
				if (player['isRadiant'] == is_radiant): #on our team
					if player['lane_efficiency'] > our_eff:
						our_eff = player['lane_efficiency']
					our_heroes.append(self.get_pretty_hero(player))
				else: #on their team
					if player['lane_efficiency'] > their_eff:
						their_eff = player['lane_efficiency']
					their_heroes.append(self.get_pretty_hero(player))
		return {
			"us": pretty_list(our_heroes, "An empty lane"),
			"won_lost": "won" if our_eff > their_eff else "lost",
			"them": pretty_list(their_heroes, "an empty lane")
		}

	# gets the story for all of the lanes
	async def get_lane_stories(self, game, is_radiant):
		story = ""
		lanes = {1: "bottom", 2: "middle", 3: "top"}
		for laneid in lanes:
			story += "• {0[us]} {0[won_lost]} {1} lane vs {0[them]}\n".format(await self.get_lane_story(game['players'], laneid, is_radiant), lanes[laneid])
		roamers = [self.get_pretty_hero(p) for p in game['players'] if p.get('is_roaming')]
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

		teamfights = await self.get_timeline_story(game, is_radiant)
		if teamfights != "":
			story += teamfights

		game_ending_state = "won" if (is_radiant == game['radiant_win']) else "lost"
		story += f"\n{end_perspective} {game_ending_state} the game at { get_pretty_duration(game['duration']) }"

		embed = discord.Embed(description=story, color=self.embed_color)
		embed.set_author(name="Story of Match {}".format(game["match_id"]), url="https://www.opendota.com/matches/{}".format(game["match_id"]))
		embed.set_footer(text="For more information, try ?match {}".format(game["match_id"]))
		await ctx.send(embed=embed)

	@commands.command(aliases=["register"])
	async def setsteam(self, ctx, steam_id : int, user: discord.User=None):
		"""Links a discord user to their steam/dota account
		*The user parameter can only be specified by the bot owner*
		
		You have to give this command either your steam32 or steam64 id. An easy way to find this is to look at the end of your dotabuff/opendota profile url.

		**Example:**
		If my dotabuff url is https://www.dotabuff.com/players/70388657
		I would do: `{cmdpfx}setsteam 70388657`
		"""

		if user is None:
			user = ctx.message.author
		elif user.id != ctx.message.author.id:
			if not checks.is_owner_check(ctx.message.author):
				await ctx.send("You aint the boss of me 😠")
				return

		if steam_id > 76561197960265728:
			steam_id -= 76561197960265728

		player = await opendota_query(f"/players/{steam_id}")

		if player.get("profile") is None:
			raise UserError("Either thats a bad id, you don't play dota, or ya haven't enabled public match data")

		userinfo = botdata.userinfo(user.id)
		userinfo.steam32 = steam_id

		await ctx.send("Linked to {}".format(player['profile']['personaname']))

	# prints the stats for the given player's latest game
	async def player_match_stats(self, steamid, match_id, ctx):
		match = await get_match(match_id)

		# Finds the player in the game which has our matching steam32 id
		player = next(p for p in match['players'] if p['account_id'] == steamid)
		if player is None:
			raise ValueError("wtf they're not in their own game")

		dotabase = self.bot.get_cog("Dotabase")
		hero_name = self.hero_info[player['hero_id']]['name']

		duration = get_pretty_duration(match['duration'], postfix=False)
		winstatus = "Won" if player["win"] != 0 else "Lost"
		game_mode = self.dota_game_strings[f"game_mode_{match['game_mode']}"]
		lobby_type = self.dota_game_strings[f"lobby_type_{match['lobby_type']}"] + " "
		if lobby_type == "Normal ":
			lobby_type = ""

		description = (f"{winstatus} a {lobby_type}**{game_mode}** match as {hero_name} in {duration}. "
					f"More info at [DotaBuff](https://www.dotabuff.com/matches/{match_id}), "
					f"[OpenDota](https://www.opendota.com/matches/{match_id}), or "
					f"[STRATZ](https://www.stratz.com/match/{match_id})")

		embed = discord.Embed(description=description, color=self.embed_color, timestamp=datetime.datetime.utcfromtimestamp(match['start_time']))

		embed.set_author(name=player['personaname'], icon_url=self.hero_info[player['hero_id']]['icon'], url="https://www.opendota.com/players/{}".format(steamid))

		embed.add_field(name="Damage", value=(
			"KDA: **{kills}**/**{deaths}**/**{assists}**\n"
			"Hero Damage: {hero_damage:,}\n"
			"Hero Healing: {hero_healing:,}\n"
			"Tower Damage: {tower_damage:,}\n".format(**player)))

		embed.add_field(name="Economy", value=(
			"Net Worth: {total_gold:,}\n"
			"Last Hits: {last_hits:,}\n"
			"Denies: {denies}\n"
			"Level: {level}\n".format(**player)))

		match_image = discord.File(await drawdota.create_match_image(match), "match.png")
		embed.set_image(url=f"attachment://{match_image.filename}")
		embed.set_footer(text=str(match_id))

		await ctx.send(embed=embed, file=match_image)

	@commands.command(aliases=["lastgame"])
	async def lastmatch(self, ctx, player=None):
		"""Gets info about the player's last dota game"""
		await ctx.channel.trigger_typing()

		steamid = await get_check_steamid(player, ctx)
		match_id = await get_lastmatch_id(steamid)
		await self.player_match_stats(steamid, match_id, ctx)

	@commands.command(aliases=["matchdetails"])
	async def match(self, ctx, match_id : int):
		"""Gets a summary of the dota match with the given id"""
		await ctx.channel.trigger_typing()

		match = await get_match(match_id)
		duration = get_pretty_duration(match['duration'], postfix=False)
		game_mode = self.dota_game_strings[f"game_mode_{match['game_mode']}"]
		lobby_type = self.dota_game_strings[f"lobby_type_{match['lobby_type']}"] + " "
		if lobby_type == "Normal ":
			lobby_type = ""

		description = (f"This {lobby_type}**{game_mode}** match ended in {duration} \n"
					f"More info at [DotaBuff](https://www.dotabuff.com/matches/{match_id}), "
					f"[OpenDota](https://www.opendota.com/matches/{match_id}), or "
					f"[STRATZ](https://www.stratz.com/match/{match_id})")

		embed = discord.Embed(description=description, 
							timestamp=datetime.datetime.utcfromtimestamp(match['start_time']), color=self.embed_color)
		embed.set_author(name="Match {}".format(match_id), url="https://www.opendota.com/matches/{}".format(match_id))

		embed.add_field(name="Game Mode", value=self.dota_game_strings[f"game_mode_{match['game_mode']}"])
		embed.add_field(name="Lobby Type", value=self.dota_game_strings[f"lobby_type_{match['lobby_type']}"])

		match_image = discord.File(await drawdota.create_match_image(match), filename="matchimage.png")

		embed.set_image(url=f"attachment://{match_image.filename}")
		embed.set_footer(text=str(match_id))
		await ctx.send(embed=embed, file=match_image)

	@commands.command()
	async def matchstory(self, ctx, match_id : int, perspective=None):
		"""Tells the story of the match from the given perspective"""
		await ctx.channel.trigger_typing()

		steamid = await get_check_steamid(None, ctx, no_error=True)

		match = await get_match(match_id)

		if perspective is None:
			player_data = next(p for p in match['players'] if p['account_id'] == steamid)
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

	@commands.command(aliases=["lastgamestory"])
	async def lastmatchstory(self, ctx, player=None):
		"""Tells the story of the player's last match

		Input must be either a discord user, a steam32 id, or a steam64 id"""
		await ctx.channel.trigger_typing()

		steamid, perspective = await get_check_steamid(player, ctx, mention=True)
		try:
			match_id = (await opendota_query(f"/players/{steamid}/matches?limit=1"))[0]['match_id']
			game = await get_match(match_id)
		except UserError:
			await ctx.send("I can't find the last game this player played")
			return
		if player is None:
			player = ctx.message.author.mention

		player_data = next(p for p in game['players'] if p['account_id'] == steamid)
		perspective += "({0}, {1})".format(self.get_pretty_hero(player_data), "Radiant" if player_data['isRadiant'] else "Dire")

		await self.tell_match_story(game, player_data['isRadiant'], ctx, perspective)

	@commands.command(aliases=["recentmatches", "recent"])
	async def matches(self, ctx, matchcount=10, player=None):
		"""Gets a list of your recent matches

		Specifiy a `matchcount` to get a specific number of matches. Default is 10
		You can also mention a user to get their recent matches

		**Example:**
		`{cmdpfx}matches 5 @PlayerPerson`"""
		steam32 = await get_check_steamid(player, ctx)

		await ctx.channel.trigger_typing()

		matches = await opendota_query(f"/players/{steam32}/recentmatches")

		if matchcount < 1:
			raise UserError("Gotta have a matchcount of 1 or more")
		if matchcount > 20:
			raise UserError("Sorries, 20 is the maximum number of matches for this command")
		if not matches:
			raise UserError("Looks like this player hasn't played any matches")

		matches = matches[:matchcount]

		embed = discord.Embed()

		embed.title = "Recent Matches"
		embed.url = f"https://www.opendota.com/players/{steam32}"

		matches_image = await drawdota.draw_matches_table(matches, self.dota_game_strings)
		matches_image = discord.File(matches_image, "matches.png")
		embed.set_image(url=f"attachment://{matches_image.filename}")

		await ctx.send(embed=embed, file=matches_image)

	@commands.command(aliases=["whois"])
	async def profile(self, ctx, player=None):
		"""Displays information about the player's dota profile

		The argument for this command can be either a steam32 id, a steam64 id, or an @mention of a discord user who has a steamid set"""
		steam32 = await get_check_steamid(player, ctx)

		await ctx.channel.trigger_typing()

		playerinfo = await opendota_query(f"/players/{steam32}")
		matches = await opendota_query(f"/players/{steam32}/matches")

		gamesplayed = len(matches)
		if gamesplayed > 0:
			winrate = "{:.2%}".format(len(list(filter(lambda m: m['radiant_win'] == (m['player_slot'] < 128), matches))) / gamesplayed)
		else:
			winrate = "0%"
		if playerinfo.get("solo_competitive_rank") is not None:
			solommr = f"**{playerinfo['solo_competitive_rank']}**"
		else:
			solommr = "not publicly displayed"

		heroes = {}
		for match in matches:
			heroes[match['hero_id']] = heroes.get(match['hero_id'], 0) + 1
		heroes = sorted(heroes.items(), key=lambda x: x[1], reverse=True)
		favs = ""
		for i in range(0,3):
			if i < len(heroes):
				if i:
					favs += ", "
				favs += self.hero_info[heroes[i][0]]['name']

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
				if i:
					recent_favs += ", "
				recent_favs += self.hero_info[heroes[i][0]]['name']

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

		overall_activity_delta = get_pretty_time((int(statistics.mean(activity_delta)) // 60) * 60)
		if recent_count:
			recent_activity_delta = get_pretty_time((int(statistics.mean(activity_delta[:recent_count])) // 60) * 60)
		else:
			recent_activity_delta = None
		# overall_activity_count = int(statistics.mean(activity_count))
		# recent_activity_count = int(statistics.mean(activity_count[:recent_count]))

		embed = discord.Embed(color=self.embed_color)

		embed.set_author(
			name=playerinfo["profile"]["personaname"], 
			icon_url=playerinfo["profile"]["avatar"], 
			url=playerinfo["profile"]["profileurl"])

		embed.add_field(name="General", value=(
			f"Winrate of **{winrate}** over **{gamesplayed}** games\n"
			f"Solo MMR: {solommr}\n"
			f"Estimated MMR: **{playerinfo.get('mmr_estimate').get('estimate')}** *(based on players in recently played games)*"))

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
			f"**Overall**: {overall_activity_delta}\n"))

		if player is None:
			player_mention = ""
		else:
			try:
				player_user = await commands.MemberConverter().convert(ctx, player)
				player_mention = f"@{player_user.nick if player_user.nick else player_user.name}"
			except commands.BadArgument:
				# This is a steamid
				player_mention = player

		embed.set_footer(text=f"For more info, try ?playerstats {player_mention}")

		rank_icon = await drawdota.dota_rank_icon(playerinfo.get("rank_tier"), playerinfo.get("leaderboard_rank"))
		rank_icon = discord.File(rank_icon, "rank.png")
		embed.set_thumbnail(url=f"attachment://{rank_icon.filename}")

		await ctx.send(embed=embed, file=rank_icon)

	@commands.command()
	async def playerstats(self, ctx, *, player=None):
		"""Gets stats from the given player's last 20 parsed games

		Note that this only cares about **parsed** games, and unparsed games will be ignored. If the player has less than 20 parsed matches, we'll use all the parsed matches available"""
		steam32 = await get_check_steamid(player, ctx)
		with ctx.channel.typing():
			await thinker.think(ctx.message)

			playerinfo = await opendota_query(f"/players/{steam32}")
			matches_info = await opendota_query(f"/players/{steam32}/matches")
			player_matches = []
			matches = []
			i = 0
			while i < len(matches_info) and len(player_matches) < 20:
				if matches_info[i].get('version', None) is not None:
					match = await get_match(matches_info[i]['match_id'])
					player_matches.append(next(p for p in match['players'] if p['account_id'] == steam32))
					matches.append(match)
					
					player_matches[-1]['party_size'] = 0
					for player in match['players']:
						if player['party_id'] == player_matches[-1]['party_id']:
							player_matches[-1]['party_size'] = player_matches[-1].get('party_size', 0) + 1
				i += 1

		await thinker.stop_thinking(ctx.message)
		if len(matches) < 2:
			await ctx.send("Not enough parsed matches!")
			return

		embed = discord.Embed(description=f"*The following are averages and percentages based on the last {len(matches)} parsed matches*", color=self.embed_color)

		embed.set_author(
			name=playerinfo["profile"]["personaname"], 
			icon_url=playerinfo["profile"]["avatar"], 
			url=f"https://www.opendota.com/players/{steam32}")

		def avg(key, round_place=0):
			x = 0
			for player in player_matches:
				if isinstance(key, LambdaType):
					val = key(player)
				else:
					val = player.get(key, 0)
				x += val
			x = round(x / len(player_matches), round_place)
			return int(x) if round_place == 0 else x

		def percent(key, round_place=0):
			count = 0
			for player in player_matches:
				if isinstance(key, LambdaType):
					success = key(player)
				else:
					success = player.get(key, 0)
				if success:
					count += 1
			count = round((count * 100) / len(player_matches), round_place)
			return int(count) if round_place == 0 else count

		chat_wheel_counts = {}
		chat_wheel_total = 0
		longest_message_heading = "Longest Chat Message"
		message_count = 0
		longest_message = None
		longest_message_match_id = None
		for match in matches:
			player = next(p for p in match['players'] if p['account_id'] == steam32)
			for message in match['chat']:
				if message.get('player_slot', -1) == player['player_slot']:
					if message["type"] == "chat":
						message_count += 1
						if longest_message is None or len(longest_message) <= len(message['key']):
							longest_message = message['key']
							longest_message_match_id = match['match_id']
					elif message["type"] == "chatwheel":
						msg_id = int(message['key'])
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
				message = self.chat_wheel_info[msg_id]
				icon = self.get_emoji("chat_wheel_sound" if message['is_sound'] else "chat_wheel_text")
				lines.append(f"{icon} {message['message']}")
			chat_wheel_text = "\n".join(lines)

		embed.add_field(name="General", value=(
			f"Winrate: {percent('win')}%\n"
			f"KDA: **{avg('kills')}**/**{avg('deaths')}**/**{avg('assists')}**\n"
			f"Game duration: {format_duration_simple(avg('duration'))}\n"
			f"In a Party: {percent(lambda p: p['party_size'] > 1)}%\n"
			f"Ranked: {percent(lambda p: p['lobby_type'] == 7)}%"))

		embed.add_field(name="Economy", value=(
			f"GPM: {avg('gold_per_min')}\n"
			f"Last Hits/min: {avg(lambda p: p['last_hits'] / (1 + (p['duration'] / 60)), 2)}\n"
			f"Farm from jungle: {avg(lambda p: 100 * p['neutral_kills'] / (1 + p['last_hits']))}%"))

		def wards_placed(p):
			obs = 0 if p.get('obs_placed') is None else p.get('obs_placed')
			sents = 0 if p.get('sen_placed') is None else p.get('sen_placed')
			return obs + sents

		embed.add_field(name="Wards placed", value=(
			f"None: {percent(lambda p: wards_placed(p) == 0)}%\n"
			f"<5: {percent(lambda p: wards_placed(p) < 5 and wards_placed(p) != 0)}%\n"
			f"<20: {percent(lambda p: wards_placed(p) < 20 and wards_placed(p) >= 5)}%\n"
			f">=20: {percent(lambda p: wards_placed(p) >= 20)}%"))

		embed.add_field(name="Heroes", value=(
			f"{self.get_emoji('attr_strength')} {percent(lambda p: self.hero_info[p['hero_id']]['attr'] == 'strength')}%\n"
			f"{self.get_emoji('attr_agility')} {percent(lambda p: self.hero_info[p['hero_id']]['attr'] == 'agility')}%\n"
			f"{self.get_emoji('attr_intelligence')} {percent(lambda p: self.hero_info[p['hero_id']]['attr'] == 'intelligence')}%\n"
			f"Randomed: {percent('randomed')}%"))

		embed.add_field(name="Laning", value=(
			f"Safe Lane: {percent(lambda p: p['lane_role'] == 1 and not p.get('is_roaming'))}%\n"
			f"Mid Lane: {percent(lambda p: p['lane_role'] == 2 and not p.get('is_roaming'))}%\n"
			f"Off Lane: {percent(lambda p: p['lane_role'] == 3 and not p.get('is_roaming'))}%\n"
			f"Jungle: {percent(lambda p: p['lane_role'] == 4 and not p.get('is_roaming'))}%\n"
			f"Roaming: {percent(lambda p: p.get('is_roaming'))}%\n"))

		embed.add_field(name="Chat Wheel", value=chat_wheel_text)

		embed.add_field(name="All Chat", value=(
			f"Messages per Game: {message_count}\n"
			f"{longest_message_heading}: {longest_message}"))

		# in a group

		await ctx.send(embed=embed)

	@commands.command()
	async def herostats(self, ctx, *, hero):
		"""Gets your stats for a hero

		Clicking on the title of the returned embed will bring you to an opendota page with all of your games with that hero.

		Example:
		`{cmdpfx}herostats tinker`

		Example:
		`{cmdpfx}herostats tinker mid`

		You can also give a lane, and then the command will return stats for games you played in that lane

		If you @mention someone in the command, it will get their hero stats instead

		Lanes can only be calculated for matches that have been parsed
		"""
		player = None

		words = hero.lower().replace("lane", "").split(" ")

		if len(ctx.message.mentions) > 0:
			if len(ctx.message.mentions) > 1:
				raise UserError("Only mention one person. Can't do stats on multiple people here.")
				return
			i = 0
			while i < len(words):
				if re.match(r'<@!?([0-9]+)>$', words[i]):
					words.pop(i)
				else:
					i += 1
			player = ctx.message.mentions[0]

		steam32 = await get_check_steamid(player, ctx)


		lane_args = [
			{
				"name": "safe lane",
				"keywords": [ "safe" ] ,
				"url_query": "&lane_role=1",
				"filter": lambda p: p.get('lane_role') == 1 and not p.get('is_roaming')
			},
			{
				"name": "mid lane",
				"keywords": [ "mid", "middle" ],
				"url_query": "&lane_role=2",
				"filter": lambda p: p.get('lane_role') == 2 and not p.get('is_roaming')
			},
			{
				"name": "offlane",
				"keywords": [ "off", "hard" ],
				"url_query": "&lane_role=3",
				"filter": lambda p: p.get('lane_role') == 3 and not p.get('is_roaming')
			},
			{
				"name": "jungle",
				"keywords": [ "jungle", "jungling" ],
				"url_query": "&lane_role=4",
				"filter": lambda p: p.get('lane_role') == 4 and not p.get('is_roaming')
			},
			{
				"name": "roaming",
				"keywords": [ "roaming", "roam", "gank", "ganking" ],
				"filter": lambda p: p.get('is_roaming')
			}
		]

		def find_lane():
			for i in range(len(words)):
				for lane in lane_args:
					if words[i] in lane["keywords"]:
						words.pop(i)
						return lane

		chosen_lane = find_lane()

		hero_text = " ".join(words)

		if hero_text == "":
			await ctx.send(f"You have to give me a hero")
			return

		hero = self.lookup_hero(hero_text)
		if not hero:
			await ctx.send(f"I'm not sure what hero \"*{hero_text}*\" is.")
			return

		projections = [ "kills", "deaths", "assists", "hero_id", "version", "lane_role", "is_roaming" ]
		projections = map(lambda p: f"project={p}", projections)
		projections = "&".join(projections)

		queryargs = f"?hero_id={hero.id}&{projections}"

		await ctx.channel.trigger_typing()
		await thinker.think(ctx.message)
		playerinfo = await opendota_query(f"/players/{steam32}")
		matches = await opendota_query(f"/players/{steam32}/matches{queryargs}")
		await thinker.stop_thinking(ctx.message)

		if chosen_lane:
			matches = list(filter(chosen_lane["filter"], matches))

		if len(matches) == 0:
			if not chosen_lane:
				await ctx.send(f"Looks like you haven't played {hero.localized_name}")
			else:
				await ctx.send(f"Looks like you haven't played any parsed matches as {hero.localized_name} in {chosen_lane['name']}")
			return

		lane_parsed_count = len(list(filter(lambda p: p['lane_role'] is not None, matches)))

		def avg(key, parsed=False, round_place=0):
			x = 0
			for match in matches:
				if parsed and not match['version']:
					continue
				if isinstance(key, LambdaType):
					val = key(match)
				else:
					val = match.get(key, 0)
				x += val
			x = round(x / (len(matches) if not parsed else lane_parsed_count), round_place)
			return int(x) if round_place == 0 else x

		def percent(key, parsed=False, round_place=0):
			count = 0
			for match in matches:
				if parsed and not match['version']:
					continue
				if isinstance(key, LambdaType):
					success = key(match)
				else:
					success = match.get(key, 0)
				if success:
					count += 1
			count = round((count * 100) / (len(matches) if not parsed else lane_parsed_count), round_place)
			return int(count) if round_place == 0 else count


		url = f"https://www.opendota.com/players/{steam32}/matches?hero_id={hero.id}"
		if chosen_lane:
			url += chosen_lane.get("url_query", "")

		embed = discord.Embed(description=(
			f"[Games Played]({url}): **{len(matches)}**\n"
			f"Winrate: **{percent(lambda p: p['radiant_win'] == (p['player_slot'] < 128), round_place=2)}%**\n"
			f"Avg KDA: **{avg('kills')}**/**{avg('deaths')}**/**{avg('assists')}**\n"), color=self.embed_color)


		embed.set_author(
			name=f"{playerinfo['profile']['personaname']} ({hero.localized_name})", 
			icon_url=self.hero_info[hero.id]["icon"],
			url=url)

		embed.set_thumbnail(url=self.hero_info[hero.id]['portrait'])

		if (not chosen_lane) and lane_parsed_count > 0:
			lanes = {
				"Safe Lane": percent(lambda p: p.get('lane_role') == 1 and not p.get('is_roaming'), parsed=True),
				"Mid Lane": percent(lambda p: p.get('lane_role') == 2 and not p.get('is_roaming'), parsed=True),
				"Off Lane": percent(lambda p: p.get('lane_role') == 3 and not p.get('is_roaming'), parsed=True),
				"Jungle": percent(lambda p: p.get('lane_role') == 4 and not p.get('is_roaming'), parsed=True),
				"Roaming": percent(lambda p: p.get('is_roaming'), parsed=True)
			}
			values = []
			for lane in lanes:
				if lanes[lane] > 0:
					values.append(f"{lane}: **{lanes[lane]}%**")
			embed.add_field(name=f"Laning ({lane_parsed_count} parsed match{'es' if lane_parsed_count > 1 else ''})", value="\n".join(values))

		await ctx.send(embed=embed)

	@commands.command()
	async def friendstats(self, ctx, player):
		"""Statistics of games played with a friend"""
		await ctx.channel.trigger_typing()
		author_id = botdata.userinfo(ctx.message.author.id).steam32
		if not author_id:
			raise SteamNotLinkedError()

		friend_id, friend_mention = await get_check_steamid(player, ctx, mention=True)
		author_mention = ctx.message.author.mention

		if author_id == friend_id:
			raise UserError("🙄 ...Try giving me someone other than yourself...")

		author_info = await opendota_query(f"/players/{author_id}")
		friend_info = await opendota_query(f"/players/{friend_id}")

		def on_same_team(match):
			heroes = match["heroes"]
			player1 = heroes[next(x for x in heroes if heroes[x].get("account_id") == author_id)]
			player2 = heroes[next(x for x in heroes if heroes[x].get("account_id") == friend_id)]
			return (player1["player_slot"] < 128) == (player2["player_slot"] < 128)
		def won_match(match):
			heroes = match["heroes"]
			player = heroes[next(x for x in heroes if heroes[x].get("account_id") == author_id)]
			return (player["player_slot"] < 128) == match["radiant_win"]

		url = f"/players/{author_id}/matches?included_account_id={friend_id}"
		matches = await opendota_query(url)
		matches = list(filter(on_same_team, matches))
		if len(matches) == 0:
			raise UserError("You haven't played any matches with them!")

		winrate = len(list(filter(won_match, matches))) / len(matches)

		def format_match(match):
			heroes = match["heroes"]
			author = heroes[next(x for x in heroes if heroes[x].get("account_id") == author_id)]
			friend = heroes[next(x for x in heroes if heroes[x].get("account_id") == friend_id)]
			timediff = time.time() - match['start_time']
			timediff -= timediff % 60
			if timediff > (60 * 60 * 24 * 30):
				timediff -= timediff % (60 * 60)
			return (
				f"{get_pretty_time(timediff)} ago, "
				f"you [{'won' if won_match(match) else 'lost'} a match](https://www.opendota.com/matches/{match['match_id']}) where "
				f"{author_mention} played **{self.hero_info[author['hero_id']]['name']}**, and "
				f"{friend_mention} played **{self.hero_info[friend['hero_id']]['name']}**")

		embed = discord.Embed(description=(
			f"[Games Played](https://www.opendota.com{url}): {len(matches)}\n"
			f"Winrate: {winrate:.2%}\n"), color=self.embed_color)

		embed.add_field(name="First Match", value=format_match(matches[-1]))
		embed.add_field(name="Most Recent Match", value=format_match(matches[0]))

		embed.set_author(
			name=f"{author_info['profile']['personaname']} + {friend_info['profile']['personaname']}", 
			url=f"https://www.opendota.com{url}")

		image = discord.File(await drawdota.combine_image_halves(author_info['profile']['avatarfull'], friend_info['profile']['avatarfull']), "profile.png")
		embed.set_thumbnail(url=f"attachment://{image.filename}")

		await ctx.send(embed=embed, file=image)

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
			raise UserError(f"It looks like match `{match_id}` hasn't been parsed by STRATZ")


		start = int(get_time(start))
		end = int(get_time(end))

		if end - start > 600:
			raise UserError("The length of this clip must be less than 10 minutes")

		if ms_per_second < 1 or ms_per_second > 655350:
			raise UserError("That is outside the bounds of the `ms_per_second` value")
		

		async with ctx.channel.typing():
			await thinker.think(ctx.message)
			try:
				image = discord.File(await drawdota.create_dota_gif(match, stratz_match, start, end, ms_per_second), "map.gif")
				await ctx.send(file=image)
			finally:
				await thinker.stop_thinking(ctx.message)

	@commands.command(aliases=["lanes"])
	async def laning(self, ctx, match_id : int = None):
		"""Creates a short description and a gif of the laning stage

		If no match id is given and the user has a steam account connected, use the most recent game"""
		await ctx.channel.trigger_typing()
		try:
			steamid = await get_check_steamid(None, ctx)
		except SteamNotLinkedError:
			steamid = None
			pass
		if match_id is None:
			if steamid is None:
				raise SteamNotLinkedError()
			match_id = await get_lastmatch_id(steamid)
		

		match = await get_match(match_id)
		if not is_parsed(match):
			raise MatchNotParsedError(match_id, "get laning info")

		stratz_match = await get_stratz_match(match_id)
		if not is_stratz_parsed(stratz_match):
			raise UserError(f"It looks like match `{match_id}` hasn't been parsed by STRATZ")

		player_data = None
		if steamid:
			player_data = next((p for p in match['players'] if p['account_id'] == steamid), None)
		perspective = player_data.get("isRadiant") if player_data else True

		embed = discord.Embed(description=await self.get_lane_stories(match, perspective))

		embed.title = f"Laning"
		embed.url = f"https://www.opendota.com/matches/{match_id}/laning"


		async with ctx.channel.typing():
			await thinker.think(ctx.message)
			try:
				image = discord.File(await drawdota.create_dota_gif(match, stratz_match, -89, 600, 100), "map.gif")
				embed.set_image(url=f"attachment://{image.filename}")
				await ctx.send(embed=embed, file=image)
			finally:
				await thinker.stop_thinking(ctx.message)


	@commands.command()
	async def parse(self, ctx, match_id : int):
		"""Requests that OpenDota parses a match

		The input should be the match_id of the match

		Note that matches from more than a couple days ago may not be able to be parsed because replay files are not saved that long"""
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

		while True:
			data = await opendota_query(f"/request/{jobId}", False)

			if data is not None:
				await asyncio.sleep(3)
			else:
				await ctx.message.remove_reaction("⏳", self.bot.user)
				await ctx.message.add_reaction("✅")
				await ctx.send(f"✅ Parsing of match {match_id} has completed!", delete_after=10)
				return




	@commands.command()
	async def opendota(self, ctx, *, query):
		"""Queries the opendota api

		You can use this to get a json file with details about players or matches etc.
		Examples:
		`{cmdpfx}opendota /players/{steamid}`
		`{cmdpfx}opendota /matches/{match_id}`

		For more options and a better explanation, check out their [documentation](https://docs.opendota.com)"""
		query = query.replace("/", " ")
		query = query.strip()
		query = "/" + "/".join(query.split(" "))

		with ctx.channel.typing():
			data = await opendota_query(query)

		filename = re.search("/([/0-9a-zA-Z]+)", query).group(1).replace("/", "_")
		filename = settings.resource(f"temp/{filename}.json")
		write_json(filename, data)
		await ctx.send(file=discord.File(filename))
		os.remove(filename)


def setup(bot):
	bot.add_cog(DotaStats(bot))