import discord
from discord.ext import commands
from __main__ import settings, botdata
from cogs.utils import checks
import aiohttp
import asyncio
import async_timeout
import string
import dota2api
import datetime
from .mangocog import *

async def opendota_query(querystring):
	async with aiohttp.get("https://api.opendota.com/api" + querystring) as r:
		if r.status == 200:
			return await r.json()
		else:
			raise ValueError("OpenDota bad response: " + r.status)

class DotaStats(MangoCog):
	"""Commands used to access Dota 2 players' stats
	"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	# prints the stats for the given player's latest game
	async def write_stats(self, userinfo):
		match_id = d2api.get_match_history(account_id=userinfo.steam64)['matches'][0]['match_id']
		game = d2api.get_match_details(match_id)
		playerinfo = d2api.get_player_summaries(int(userinfo.steam64))['players'][0]
		dotabase = self.bot.get_cog("Dotabase")

		# Finds the player in the game which has our matching steam32 id
		player = next(p for p in game['players'] if int(p['account_id']) == userinfo.steam32)

		if player is None:
			raise ValueError("wtf hes not in is own game")

		winstatus = "Won" if (player['player_slot'] < 5 and game['radiant_win'] is True) or (player['player_slot'] >= 5 and game['radiant_win'] is False) else "Lost"

		description = ("{0} a game as {1} in {2} \n"
					"More info at [DotaBuff](https://www.dotabuff.com/matches/{3}) or [OpenDota](https://www.opendota.com/matches/{3}) "
					.format(winstatus, player['hero_name'], datetime.timedelta(seconds=game['duration']), match_id))

		embed = discord.Embed(description=description)

		heroicon = await dotabase.get_hero_icon(int(player['hero_id']))

		embed.set_author(name=playerinfo['personaname'], icon_url=heroicon)

		embed.add_field(name="General", value=(
			"Kills: {}\n"
			"Deaths: {}\n"
			"Assists: {}\n"
			"Hero Dmg: {}\n".format(player['kills'], player['deaths'], player['assists'], player['hero_damage'])))

		embed.add_field(name="Economy", value=(
			"GPM: {}\n"
			"Net Worth: {}\n"
			"Last Hits: {}\n".format(player['gold_per_min'], int(player['gold_spent']) + int(player['gold']), player['last_hits'])))

		embed.add_field(name="Experience", value=(
			"XPM: {}\n"
			"Level: {}\n"
			"Denies: {}\n".format(player['xp_per_min'], player['level'], player['denies'])))

		await self.bot.say(embed=embed)


	@commands.command(pass_context=True)
	async def setsteam(self, ctx, steam_id : int, user: discord.User=None):
		"""Links a discord user to their steam/dota accont

		The user parameter can only be specified by the bot owner
		
		An easy way get your steam_id is to go to your profile page in steam, right click anywhere, and select 'Copy Page URL.' Then paste that somewhere, and get the number at the end of the url. Thats your steam_id. Now just do ?addsteam <thenumber> If its not a number, you gotta look somewhere else. the the end of the url for your profile on dotabuff or something.
		"""

		if user is None:
			user = ctx.message.author
		else:
			if not await checks.is_owner_check(ctx):
				await self.bot.say("You aint the boss of me 😠")
				return

		if steam_id < 76561197960265728:
			steam_id += 76561197960265728

		playerinfos = d2api.get_player_summaries(steam_id)['players']

		if len(playerinfos) != 1:
			await self.bot.say("Dat dont look liek a valid steam id")
			return

		try:
			hist = d2api.get_match_history(steam_id)
		except dota2api.src.exceptions.APIError as e:
			await self.bot.say("Looks like either ya don't play dota, or ya haven't enabled public match data.")
			return

		userinfo = botdata.userinfo(user.id)
		userinfo.steam64 = steam_id

		await self.bot.say("You've been linked to {}".format(playerinfos[0]['personaname']))

	@commands.command(pass_context=True)
	async def lastgame(self, ctx):
		"""Gets info about your last dota game"""
		userinfo = botdata.userinfo(ctx.message.author.id)
		if userinfo.steam64 is None:
			await self.bot.say("Ya ain't got no steam id linked to ya yet. Do `?setsteam <steam_ID>`")
		else:
			await self.bot.send_typing(ctx.message.channel)
			await self.write_stats(userinfo)

	@commands.command(pass_context=True)
	async def whois(self, ctx, user : discord.User):
		"""Displays information about the user's dota profile"""
		userinfo = botdata.userinfo(user.id)

		if userinfo.steam64 is None:
			await self.bot.say("I haven't the faintest")
			return

		await self.bot.send_typing(ctx.message.channel)

		playerinfo = await opendota_query("/players/{}".format(userinfo.steam32))
		playerwl = await opendota_query("/players/{}/wl".format(userinfo.steam32))
		gamesplayed = playerwl["win"] + playerwl["lose"]
		winrate = "{:.2%}".format(playerwl["win"] / gamesplayed)
		if playerinfo.get("solo_competitive_rank") is not None:
			solommr = "last displayed as {}".format(playerinfo["solo_competitive_rank"])
		else:
			solommr = "not publicly displayed"

		hero_id_dict = await self.bot.get_cog("Dotabase").get_hero_id_dict()

		heroes = await opendota_query("/players/{}/heroes".format(userinfo.steam32))
		favs = ""
		for i in range(0,3):
			favs += hero_id_dict[int(heroes[i]["hero_id"])] + ", "
		favs = favs[:-2]

		heroes = await opendota_query("/players/{}/heroes?date=60".format(userinfo.steam32))
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
			"[DotaBuff](https://www.dotabuff.com/players/{1})".format(playerinfo["profile"]["profileurl"], userinfo.steam32)))

		embed.add_field(name="Heroes", inline=False, value=(
			"[Recent Favs](https://www.opendota.com/players/{0}/heroes?date=60) {1}\n"
			"[Overall Favs](https://www.opendota.com/players/{0}/heroes) {2}\n".format(userinfo.steam32, recent_favs, favs)))

		await self.bot.say(embed=embed)


def setup(bot):
	global d2api
	try:
		import dota2api
		d2api = dota2api.Initialise(settings.steamapikey)
	except:
		raise ModuleNotFound("Either dota2api isnt installed, or yourur steam api key is not valid")
	bot.add_cog(DotaStats(bot))