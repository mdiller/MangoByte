import discord
from discord.ext import commands
from __main__ import settings, botdata, thinker
from cogs.utils import checks
from cogs.utils import helpers
import aiohttp
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
from types import *
from .mangocog import *

async def opendota_query(querystring, rate_limit=True):
	url = "https://api.opendota.com/api" + querystring
	if rate_limit:
		await asyncio.sleep(0.2)
	async with aiohttp.get(url) as r:
		if r.status == 200:
			return json.loads(await r.text(), object_pairs_hook=OrderedDict)
		elif r.status == 404:
			raise UserError("Dats not a valid query. Take a look at the OpenDota API Documentation: https://docs.opendota.com")
		elif r.status == 521:
			raise UserError("Looks like the OpenDota API is down or somethin, so ya gotta wait a sec")
		else:
			print("OpenDota api errored on GET: '{}'".format(url))
			raise UserError("OpenDota said we did things wrong 😢. status code: {}".format(r.status))

# rate_limit = false if this is the only query we're sending
async def get_match(match_id, rate_limit=True):
	match_file = settings.resource(f"cache/match_{match_id}.json")
	if os.path.isfile(match_file):
		return helpers.read_json(match_file)
	else:
		match = await opendota_query("/matches/{}".format(match_id), rate_limit)
		if match.get("version", None) is not None:
			if not os.path.exists(os.path.dirname(match_file)):
				os.makedirs(os.path.dirname(match_file))
			helpers.write_json(match_file, match)
		return match

async def get_match_image(matchid, is_parsed):
	# Make sure to check that the match id is valid before calling this
	url = "http://dotabase.me/image-api/request.php?match={}".format(matchid)
	url += "&parsed={}".format("true" if is_parsed else "false")
	try:
		with async_timeout.timeout(8):
			async with aiohttp.post(url) as r:
				if r.status == 200:
					data = json.loads(await r.text(), object_pairs_hook=OrderedDict)
					return data['file']
				else:
					print("Dotabase image-api errored on POST: '{}'".format(url))
					raise UserError("Errored on generating match image".format(r.status))
	except asyncio.TimeoutError:
		raise UserError("TimeoutError while generating match image: try again")

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

def get_pretty_time(unixtime):
	if unixtime == 0:
		return None
	is_after = unixtime > 0
	unixtime = abs(unixtime)
	time = {"days": (unixtime // 86400) % 86400, "hours": (unixtime // 3600) % 3600, "minutes": (unixtime // 60) % 60, "seconds": unixtime % 60}
	format_arr = []
	if time["days"] > 0:
		format_arr.append(s_if_plural("{days} day", time["days"]))
	if time["hours"] > 0:
		format_arr.append(s_if_plural("{hours} hour", time["hours"]))
	if time["minutes"] > 0:
		format_arr.append(s_if_plural("{minutes} minute", time["minutes"]))
	if time["seconds"] > 0:
		format_arr.append(s_if_plural("{seconds} second", time["seconds"]))
	format_str = pretty_list(format_arr)
	return format_str.format(**time)

def get_pretty_duration(duration, postfix=True):
	if duration == 0:
		return "the exact start of the game"
	is_after = duration > 0
	result = get_pretty_time(duration)
	if postfix:
		result += " in" if is_after else " before the game started"
	return result

def format_duration_simple(duration):
	if duration >= 3600:
		return f"{int(duration / 3600)}:{int((duration / 60) % 60):02}:{duration % 60:02}"
	else:
		return f"{int((duration / 60) % 60)}:{duration % 60:02}"


def is_parsed(match_json):
	return match_json.get("version", None) is not None

# gets the steam32 id from the user or steamid and checks that it is valid before returning
async def get_check_steamid(steamid, ctx=None):
	is_author = steamid is None
	if is_author:
		steamid = ctx.message.author

	try:
		steamid = int(steamid)
	except (ValueError, TypeError):
		pass # This either this is a discord user or an invalid argument


	if isinstance(steamid, int):
		if steamid > 76561197960265728:
			steamid -= 76561197960265728

		# Don't have to rate limit here because this will be first query ran
		player = await opendota_query("/players/{}".format(steamid), rate_limit=False)

		if player.get("profile") is None:
			raise UserError("Either this person doesn't play dota, or they haven't enabled public match data")
		return steamid


	if not isinstance(steamid, discord.User):
		try:
			steamid = commands.MemberConverter(ctx, steamid).convert()
		except commands.BadArgument:
			raise UserError("Ya gotta @mention a user who has been linked to a steam id, or just give me a steamid")

	userinfo = botdata.userinfo(steamid.id)
	if userinfo.steam32 is None:
		if is_author:
			raise UserError("Yer steam account isn't linked to yer discord account yet.\nTry doin `?help setsteam` to see how to link a steam account.")
		else:
			raise UserError(f"{steamid.name} doesn't have a steam account linked. They should try `?help setsteam` to see how to link their steam account.")
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

	async def init_dicts(self):
		dotabase = self.bot.get_cog("Dotabase")
		self.hero_info = await dotabase.get_hero_infos()
		self.hero_aliases = dotabase.hero_aliases

	def get_pretty_hero(self, player):
		dotabase = self.bot.get_cog("Dotabase")
		return "**{}**".format(self.hero_info[player['hero_id']]['name'])

	async def get_teamfights(self, game, is_radiant):
		teamfights = []
		for teamfight in game['teamfights']:
			net_gain = 0
			our_dead = []
			their_dead = []
			for i in range(0, len(teamfight['players'])):
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
		return story

	async def tell_match_story(self, game, is_radiant, perspective=None):
		if not is_parsed(game):
			raise UserError("This game must be parsed before I can create a story")

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
		await self.bot.say(embed=embed)

	# prints the stats for the given player's latest game
	async def player_match_stats(self, steamid, matchid):
		game = await get_match(matchid)

		# Finds the player in the game which has our matching steam32 id
		player = next(p for p in game['players'] if p['account_id'] == steamid)
		if player is None:
			raise ValueError("wtf they're not in their own game")

		dotabase = self.bot.get_cog("Dotabase")
		hero_name = self.hero_info[player['hero_id']]['name']

		winstatus = "Won" if player["win"] != 0 else "Lost"

		description = ("{0} a game as {1} in {2} \n"
					"More info at [DotaBuff](https://www.dotabuff.com/matches/{3}), "
					"[OpenDota](https://www.opendota.com/matches/{3}), or "
					"[Stratz](https://www.stratz.com/match/{3})"
					.format(winstatus, hero_name, get_pretty_duration(game['duration'], postfix=False), matchid))

		embed = discord.Embed(description=description, color=self.embed_color, timestamp=datetime.datetime.utcfromtimestamp(game['start_time']))

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

		embed.set_image(url=await get_match_image(matchid, is_parsed(game)))
		embed.set_footer(text="Started".format(matchid))

		await self.bot.say(embed=embed)


	@commands.command(pass_context=True, aliases=["register"])
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
		else:
			if not checks.is_owner_check(ctx.message.author):
				await self.bot.say("You aint the boss of me 😠")
				return

		if steam_id > 76561197960265728:
			steam_id -= 76561197960265728

		player = await opendota_query("/players/{}".format(steam_id), False)

		if player.get("profile") is None:
			raise UserError("Either thats a bad id, you don't play dota, or ya haven't enabled public match data")

		userinfo = botdata.userinfo(user.id)
		userinfo.steam32 = steam_id

		await self.bot.say("Linked to {}".format(player['profile']['personaname']))

	@commands.command(pass_context=True, aliases=["lastgame"])
	async def lastmatch(self, ctx, player=None):
		"""Gets info about the player's last dota game"""
		await self.bot.send_typing(ctx.message.channel)
		steamid = await get_check_steamid(player, ctx)
		matchid = (await opendota_query("/players/{}/matches?limit=1".format(steamid), False))[0]["match_id"]
		await self.player_match_stats(steamid, matchid)

	@commands.command(pass_context=True, aliases=["matchdetails"])
	async def match(self, ctx, match_id : int):
		"""Gets a summary of the dota match with the given id"""
		await self.bot.send_typing(ctx.message.channel)
		try:
			game = await get_match(match_id)
		except UserError:
			await self.bot.say("Looks like thats not a valid match id")
			return

		description = ("Game ended in {0} \n"
					"More info at [DotaBuff](https://www.dotabuff.com/matches/{1}), "
					"[OpenDota](https://www.opendota.com/matches/{1}), or "
					"[Stratz](https://www.stratz.com/match/{1})"
					.format(get_pretty_duration(game['duration'], postfix=False), match_id))

		embed = discord.Embed(description=description, 
							timestamp=datetime.datetime.utcfromtimestamp(game['start_time']), color=self.embed_color)
		embed.set_author(name="Match {}".format(match_id), url="https://www.opendota.com/matches/{}".format(match_id))
		embed.set_image(url=await get_match_image(match_id, is_parsed(game)))
		embed.set_footer(text="Started")
		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def matchstory(self, ctx, match_id : int, perspective="radiant"):
		"""Tells the story of the match from the given perspective"""
		await self.bot.send_typing(ctx.message.channel)
		if perspective.lower() == "radiant":
			is_radiant = True
		elif perspective.lower() == "dire":
			is_radiant = False
		else:
			raise UserError("Perspective must be either radiant or dire")
		try:
			game = await get_match(match_id, False)
		except UserError:
			await self.bot.say("Looks like thats not a valid match id")
			return

		await self.tell_match_story(game, is_radiant)

	@commands.command(pass_context=True, aliases=["lastgamestory"])
	async def lastmatchstory(self, ctx, player=None):
		"""Tells the story of the player's last match

		Input must be either a discord user, a steam32 id, or a steam64 id"""
		await self.bot.send_typing(ctx.message.channel)
		steamid = await get_check_steamid(player, ctx)
		try:
			match_id = (await opendota_query("/players/{}/matches?limit=1".format(steamid)))[0]['match_id']
			game = await get_match(match_id, False)
		except UserError:
			await self.bot.say("I can't find the last game this player played")
			return
		if player is None:
			player = ctx.message.author.mention

		player_data = next(p for p in game['players'] if p['account_id'] == steamid)
		is_radiant = player_data['isRadiant']
		if player.startswith('<'):
			perspective = player
		else:
			perspective = "[{personaname}](https://www.opendota.com/players/{account_id})".format(**player_data)
		perspective += "({0}, {1})".format(self.get_pretty_hero(player_data), "Radiant" if is_radiant else "Dire")

		await self.tell_match_story(game, is_radiant, perspective)


	@commands.command(pass_context=True, aliases=["whois"])
	async def profile(self, ctx, player=None):
		"""Displays information about the player's dota profile

		The argument for this command can be either a steam32 id, a steam64 id, or an @mention of a discord user who has a steamid set"""
		steam32 = await get_check_steamid(player, ctx)

		await self.bot.send_typing(ctx.message.channel)

		playerinfo = await opendota_query(f"/players/{steam32}", False)
		matches = await opendota_query(f"/players/{steam32}/matches")
		gamesplayed = len(matches)
		winrate = "{:.2%}".format(len(list(filter(lambda m: m['radiant_win'] == (m['player_slot'] < 128), matches))) / gamesplayed)
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
			f"Estimated MMR: **{playerinfo.get('mmr_estimate').get('estimate')}** *(based players in recently played games)*"))

		embed.add_field(name="Profiles", value=(
			f"[Steam]({playerinfo['profile']['profileurl']})\n"
			f"[OpenDota](https://www.opendota.com/players/{steam32})\n"
			f"[DotaBuff](https://www.dotabuff.com/players/{steam32})\n"
			f"[Stratz](https://www.stratz.com/player/{steam32})"))

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
				player_user = commands.MemberConverter(ctx, player).convert()
				player_mention = f"@{player_user.nick if player_user.nick else player_user.name}"
			except commands.BadArgument:
				# This is a steamid
				player_mention = player

		embed.set_footer(text=f"For more info, try ?playerstats {player_mention}")

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def playerstats(self, ctx, *, player=None):
		"""Gets stats from the given player's last 20 parsed games

		Note that this only cares about **parsed** games, and unparsed games will be ignored. If the player has less than 20 parsed matches, we'll use all the parsed matches available"""
		steam32 = await get_check_steamid(player, ctx)
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
				for player in match['players']:
					if player['party_id'] == player_matches[-1]['party_id']:
						player_matches[-1]['party_size'] = player_matches[-1].get('party_size', 0) + 1
			i += 1

		await thinker.stop_thinking(ctx.message)
		if len(matches) < 2:
			await self.bot.say("Not enough parsed matches!")
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

		longest_message_heading = "Longest Chat Message"
		message_count = 0
		longest_message = None
		longest_message_matchid = None
		for match in matches:
			player = next(p for p in match['players'] if p['account_id'] == steam32)
			for message in match['chat']:
				if message.get('player_slot', -1) == player['player_slot']:
					message_count += 1
					if longest_message is None or len(longest_message) <= len(message['key']):
						longest_message = message['key']
						longest_message_matchid = match['match_id']
		message_count = int(round(message_count / len(matches)))
		if longest_message is not None:
			longest_message = f"\"{longest_message}\""
			longest_message_heading = f"[{longest_message_heading}](https://www.opendota.com/matches/{longest_message_matchid}/chat)"

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

		embed.add_field(name="Other", value=(
			f"Trees eaten: {avg(lambda p: p['item_uses'].get('tango', 0))}\n"
			f"TPs used: {avg(lambda p: p['item_uses'].get('tpscroll', 0))}"))

		embed.add_field(name="Communication", value=(
			f"Pings: {avg('pings')}\n"
			f"Chat Messages: {message_count}\n"
			f"{longest_message_heading}: {longest_message}"))

		# in a group

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def herostats(self, ctx, *, hero):
		"""Gets your stats for a hero

		Clicking on the title of the returned embed will bring you to an opendota page with all of your games with that hero.

		Example:
		`{cmdpfx}herostats tinker`

		Example:
		`{cmdpfx}herostats tinker mid`

		You can also give a lane, and then the command will return stats for games you played in that lane

		Lanes can only be calculated for matches that have been parsed
		"""
		steam32 = await get_check_steamid(None, ctx)

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

		words = hero.lower().replace("lane", "").split(" ")

		chosen_lane = None
		for i in range(len(words)):
			for lane in lane_args:
				if words[i] in lane["keywords"]:
					words.pop(i)
					i -= 1
					if chosen_lane is None:
						chosen_lane = lane
					else:
						raise UserError("Only specify one lane plz")


		hero = " ".join(words)

		if hero not in self.hero_aliases:
			await self.bot.say(f"I'm not sure what hero \"*{hero}*\" is.")
			return
		hero_id = self.hero_aliases[hero]

		projections = [ "kills", "deaths", "assists", "hero_id", "version", "lane_role" ]
		projections = map(lambda p: f"project={p}", projections)
		projections = "&".join(projections)

		queryargs = f"?hero_id={hero_id}&{projections}"

		await thinker.think(ctx.message)
		playerinfo = await opendota_query(f"/players/{steam32}")
		matches = await opendota_query(f"/players/{steam32}/matches{queryargs}")
		await thinker.stop_thinking(ctx.message)

		if chosen_lane:
			matches = list(filter(chosen_lane["filter"], matches))

		if len(matches) == 0:
			if not chosen_lane:
				await self.bot.say(f"Looks like you haven't played {self.hero_info[hero_id]['name']}")
			else:
				await self.bot.say(f"Looks like you haven't played any parsed matches as {self.hero_info[hero_id]['name']} in {chosen_lane['name']}")
			return

		parsed_count = len(list(filter(lambda p: p['version'] is not None, matches)))

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
			x = round(x / (len(matches) if not parsed else parsed_count), round_place)
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
			count = round((count * 100) / (len(matches) if not parsed else parsed_count), round_place)
			return int(count) if round_place == 0 else count


		embed = discord.Embed(description=(
			f"Games Played: **{len(matches)}**\n"
			f"Winrate: **{percent(lambda p: p['radiant_win'] == (p['player_slot'] < 128), round_place=2)}%**\n"
			f"Avg KDA: **{avg('kills')}**/**{avg('deaths')}**/**{avg('assists')}**\n"), color=self.embed_color)


		url = f"https://www.opendota.com/players/{steam32}/matches?hero_id={hero_id}"
		if chosen_lane:
			url += chosen_lane.get("url_query", "")

		embed.set_author(
			name=f"{playerinfo['profile']['personaname']} ({self.hero_info[hero_id]['name']})", 
			icon_url=self.hero_info[hero_id]["icon"],
			url=url)

		embed.set_thumbnail(url=self.hero_info[hero_id]['portrait'])

		if (not chosen_lane) and parsed_count > 0:
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
			embed.add_field(name=f"Laning ({parsed_count} parsed match{'es' if parsed_count > 1 else ''})", value="\n".join(values))

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def opendota(self, ctx, *, query):
		"""Queries the opendota api

		You can use this to get a json file with details about players or matches etc.
		Examples:
		`{cmdpfx}opendota /players/{steamid}`
		`{cmdpfx}opendota /matches/{matchid}`

		For more options and a better explanation, check out their [documentation](https://docs.opendota.com)"""
		query = query.replace("/", " ")
		query = query.strip()
		query = "/" + "/".join(query.split(" "))

		await self.bot.send_typing(ctx.message.channel)
		data = await opendota_query(query)

		filename = re.search("/([/0-9a-zA-Z]+)", query).group(1).replace("/", "_")
		filename = settings.resource(f"temp/{filename}.json")
		helpers.write_json(filename, data)
		await self.bot.send_file(ctx.message.channel, filename)
		os.remove(filename)


	@commands.command(pass_context=True)
	async def opendotasql(self, ctx, *, sql):
		"""Submits an sql query to the opendota database

		Example:
		`{cmdpfx}opendotasql SELECT * FROM matches limit 10`

		Note that you should always have a limit argument at the end, as the api will stall if you request too many rows

		You can check out their [create_tables script](https://github.com/odota/core/blob/master/sql/create_tables.sql) to get an idea of the structure of the database
		"""
		match = re.search("limit ([0-9]+)", sql)
		if not match or int(match.group(1)) > 100:
			await self.bot.say("You gotta give a reasonable limit for these queries, otherwise they will not complete. Try adding `limit 10` to the end of that.")
			return
		query = "/explorer?sql={}".format(urllib.parse.quote(sql, safe=''))
		print(query)

		await self.bot.send_typing(ctx.message.channel)
		data = await opendota_query(query)

		filename = settings.resource(f"temp/query_results.json")
		helpers.write_json(filename, data)
		await self.bot.send_file(ctx.message.channel, filename)
		os.remove(filename)


def setup(bot):
	bot.add_cog(DotaStats(bot))