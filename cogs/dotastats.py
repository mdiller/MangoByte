import discord
from discord.ext import commands
from __main__ import settings, botdata
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
from .mangocog import *

async def opendota_query(querystring):
	url = "https://api.opendota.com/api" + querystring
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

# gets the steam32 id from the user or steamid and checks that it is valid before returning
async def get_check_steamid(steamid, ctx=None):
	is_author = steamid == None
	if is_author:
		steamid = ctx.message.author

	try:
		steamid = int(steamid)
	except (ValueError, TypeError):
		pass # This either this is a discord user or an invalid argument


	if isinstance(steamid, int):
		if steamid > 76561197960265728:
			steamid -= 76561197960265728

		player = await opendota_query("/players/{}".format(steamid))

		if player.get("profile") is None:
			raise UserError("Either this person doesnt play dota, or they haven't enabled public match data")
		return steamid


	if not isinstance(steamid, discord.User):
		try:
			steamid = commands.MemberConverter(ctx, steamid).convert()
		except commands.BadArgument:
			raise UserError("Ya gotta give me a steamid or a @reference to a user who has been linked to a steam id.")

	userinfo = botdata.userinfo(steamid.id)
	if userinfo.steam32 is None:
		if is_author:
			raise UserError("Ya don't got a have a steamid linked to yer account. Yer gonna have to do `?setsteam <steamid>`.")
		else:
			raise UserError(steamid.name + " doesnt have a steamid linked. They're gonna have to do '?setsteam <steamid>' before you can do that.")
	return userinfo.steam32






class DotaStats(MangoCog):
	"""Commands used to access Dota 2 players' stats
	"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	# prints the stats for the given player's latest game
	async def player_match_stats(self, steamid, matchid):
		game = await opendota_query("/matches/{}".format(matchid))
		replay_parsed = game.get("radiant_gold_adv") is not None

		# Finds the player in the game which has our matching steam32 id
		player = next(p for p in game['players'] if p['account_id'] == steamid)
		if player is None:
			raise ValueError("wtf they're not in their own game")

		dotabase = self.bot.get_cog("Dotabase")
		hero_name = (await dotabase.get_hero_id_dict())[player['hero_id']]

		winstatus = "Won" if player["win"] != 0 else "Lost"

		description = ("{0} a game as {1} in {2} \n"
					"More info at [DotaBuff](https://www.dotabuff.com/matches/{3}) or [OpenDota](https://www.opendota.com/matches/{3}) "
					.format(winstatus, hero_name, datetime.timedelta(seconds=game['duration']), matchid))

		embed = discord.Embed(description=description)

		lane_dict = { 1:"Safelane", 2:"Middle Lane", 3:"Offlane", 4:"Jungle/Roaming" }

		heroicon = await dotabase.get_hero_icon(player['hero_id'])

		embed.set_author(name=player['personaname'], icon_url=heroicon)

		embed.add_field(name="General", value=(
			"Kills: {}\n"
			"Deaths: {}\n"
			"Assists: {}\n"
			"Hero Dmg: {}\n".format(player['kills'], player['deaths'], player['assists'], player['hero_damage'])))

		embed.add_field(name="Economy", value=(
			"GPM: {}\n"
			"Net Worth: {}\n"
			"Last Hits: {}\n".format(player['gold_per_min'], player['gold_spent'] + player['gold'], player['last_hits'])))

		embed.add_field(name="Experience", value=(
			"XPM: {}\n"
			"Level: {}\n"
			"Denies: {}\n".format(player['xp_per_min'], player['level'], player['denies'])))

		# if replay_parsed:
		# 	embed.add_field(name="Other", value=(
		# 		"Lane: {}\n"
		# 		"Pings: {}\n"
		# 		"APM: {}\n".format(lane_dict.get(player.get("lane_role")), player.get("pings", "Unavailable"), player.get("actions_per_min", "Unavailable"))))


		# if not replay_parsed:
		# 	embed.set_footer(text="Some data not available for this game")

		await self.bot.say(embed=embed)


	@commands.command(pass_context=True)
	async def setsteam(self, ctx, steam_id : int, user: discord.User=None):
		"""Links a discord user to their steam/dota account

		The user parameter can only be specified by the bot owner
		
		An easy way get your steamid is to go to your dotabuff profile page and copy the number that is at the end of the url
		"""

		if user is None:
			user = ctx.message.author
		else:
			if not await checks.is_owner_check(ctx):
				await self.bot.say("You aint the boss of me 😠")
				return

		if steam_id > 76561197960265728:
			steam_id -= 76561197960265728

		player = await opendota_query("/players/{}".format(steam_id))

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
		matchid = (await opendota_query("/players/{}/matches?limit=1".format(steamid)))[0]["match_id"]
		await self.player_match_stats(steamid, matchid)

	@commands.command(pass_context=True, aliases=["matchdetails"])
	async def match(self, ctx, match_id : int):
		"""Gets a summary of the dota match with the given id"""
		await self.bot.send_typing(ctx.message.channel)
		try:
			game = await opendota_query("/matches/{}".format(match_id))
		except UserError:
			await self.bot.say("Looks like thats not a valid match id")
			return

		tempfile = "{}temp/match_{}.png".format(settings.resourcedir, match_id)
		webkit2png = settings.resourcedir + "scripts/webkit2png.js"
		url = "http://dotabase.me/image-api/matches.php?match={}".format(match_id)
		helpers.run_command(["phantomjs", webkit2png, url, tempfile])
		await self.bot.send_file(ctx.message.channel, tempfile)
		os.remove(tempfile)

	@commands.command(pass_context=True, aliases=["whois"])
	async def profile(self, ctx, player=None):
		"""Displays information about the player's dota profile

		The argument for this command can be either a steam32 id, a steam64 id, or an @reference to a discord user who has a steamid set"""
		steam32 = await get_check_steamid(player, ctx)

		await self.bot.send_typing(ctx.message.channel)

		playerinfo = await opendota_query("/players/{}".format(steam32))
		playerwl = await opendota_query("/players/{}/wl".format(steam32))
		gamesplayed = playerwl["win"] + playerwl["lose"]
		winrate = "{:.2%}".format(playerwl["win"] / gamesplayed)
		if playerinfo.get("solo_competitive_rank") is not None:
			solommr = "last displayed as {}".format(playerinfo["solo_competitive_rank"])
		else:
			solommr = "not publicly displayed"

		hero_id_dict = await self.bot.get_cog("Dotabase").get_hero_id_dict()

		heroes = await opendota_query("/players/{}/heroes".format(steam32))
		favs = ""
		for i in range(0,3):
			favs += hero_id_dict[int(heroes[i]["hero_id"])] + ", "
		favs = favs[:-2]

		heroes = await opendota_query("/players/{}/heroes?date=60".format(steam32))
		recent_favs = ""
		for i in range(0,3):
			recent_favs += hero_id_dict[int(heroes[i]["hero_id"])] + ", "
		recent_favs = recent_favs[:-2]


		embed = discord.Embed()

		embed.set_author(
			name=playerinfo["profile"]["personaname"], 
			icon_url=playerinfo["profile"]["avatar"], 
			url=playerinfo["profile"]["profileurl"])

		embed.add_field(name="General", value=(
			"Winrate of {} over {} games, "
			"Solo MMR {}, and based on players in games played recently, "
			"MMR estimated to be {}.".format(winrate, gamesplayed, solommr, playerinfo["mmr_estimate"]["estimate"])))

		embed.add_field(name="Profiles", value=(
			"[Steam]({0})\n"
			"[OpenDota](https://www.opendota.com/players/{1})\n"
			"[DotaBuff](https://www.dotabuff.com/players/{1})".format(playerinfo["profile"]["profileurl"], steam32)))

		embed.add_field(name="Heroes", inline=False, value=(
			"[Recent Favs](https://www.opendota.com/players/{0}/heroes?date=60) {1}\n"
			"[Overall Favs](https://www.opendota.com/players/{0}/heroes) {2}\n".format(steam32, recent_favs, favs)))

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def opendota(self, ctx, *, query):
		"""queries the opendota api

		You can use this to get a json file with details about players or matches etc.
		ex:
		?opendota /players/{steamid}
		?opendota /matches/{matchid}

		For more options and a better explanation, check out their documentation: https://docs.opendota.com"""
		query = query.replace("/", " ")
		query = query.strip()
		query = "/" + "/".join(query.split(" "))

		await self.bot.send_typing(ctx.message.channel)
		data = await opendota_query(query)

		filename = re.search("/([/0-9a-zA-Z]+)", query).group(1).replace("/", "_")
		filename = "{}temp/{}.json".format(settings.resourcedir, filename)
		helpers.write_json(filename, data)
		await self.bot.send_file(ctx.message.channel, filename)
		os.remove(filename)


	@commands.command(pass_context=True)
	async def opendotasql(self, ctx, *, sql):
		"""submits an sql query to the opendota database

		Example:
		?opendotasql SELECT * FROM matches limit 10

		see https://github.com/odota/core/blob/master/sql/create_tables.sql to get an idea of the structure of the database
		"""
		match = re.search("limit ([0-9]+)", sql)
		if not match or int(match.group(1)) > 100:
			await self.bot.say("You gotta give a reasonable limit for these queries, otherwise they will not complete. Try adding `limit 10` to the end of that.")
			return
		query = "/explorer?sql={}".format(html.escape(sql))
		query = query.replace(" ", "%20")

		await self.bot.send_typing(ctx.message.channel)
		data = await opendota_query(query)

		filename = "{}temp/{}.json".format(settings.resourcedir, "query_results")
		helpers.write_json(filename, data)
		await self.bot.send_file(ctx.message.channel, filename)
		os.remove(filename)


def setup(bot):
	bot.add_cog(DotaStats(bot))