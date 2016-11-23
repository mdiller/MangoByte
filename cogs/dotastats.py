import discord
from discord.ext import commands
from __main__ import settings, botdata
import asyncio
import string
import dota2api
import datetime

class DotaStats:
	"""Commands used to access Dota 2 players' stats
	"""

	def __init__(self, bot):
		self.bot = bot

	# prints the stats for the given player's latest game
	async def write_stats(self, userinfo):
		match_id = d2api.get_match_history(account_id=int(userinfo.steam))['matches'][0]['match_id']
		game = d2api.get_match_details(match_id)
		playerinfo = d2api.get_player_summaries(int(userinfo.steam))['players'][0]
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
			"Last Hits: {}\n"
			"Net Worth: {}\n".format(player['gold_per_min'], player['last_hits'], int(player['gold_spent']) + int(player['gold']))))

		embed.add_field(name="Experience", value=(
			"Level: {}\n"
			"XPM: {}\n"
			"Denies: {}\n".format(player['level'], player['xp_per_min'], player['denies'])))

		embed.set_footer(text="Data extracted from the Dota2 REST API", icon_url="http://dotabase.me/resources/images/dota.png")


		await self.bot.say(embed=embed)


	@commands.command(pass_context=True)
	async def setsteam(self, ctx, steam_id : int):
		"""Adds a dota player to the dota stat tracker, vie their steam id
		
		To get your steam_id, an easy way is to go to your profile page in steam, right click anywhere, and select 'Copy Page URL.' Then paste that somewhere, and get the number at the end of the url. It should start with a 7 and be like 16 characters or something. Thats your steam_id. Now just do ?addsteam <thenumber>.
		"""
		userinfo = botdata.userinfo(ctx.message.author.id)

		try:
			hist = d2api.get_match_history(steam_id)
		except Exception as e:
			print(e.message)
			await self.bot.say("Either you must enable Expose Public Match Data in your DotA 2 client, or that is an invalid ID")
			return

		userinfo.steam = str(steam_id)

		await self.bot.say( "I added " + str(ctx.message.author) + " to the list of players. NOW I'M WATCHING YOU")

	@commands.command(pass_context=True, hidden=True)
	async def setsteam(self, ctx, steam_id : int):
		await self.bot.say("?setsteam is deprecated, use ?setsteam instead")

	@commands.command(pass_context=True, hidden=True)
	async def stats(self, ctx):
		await self.bot.say("?stats is deprecated, use ?lastgame instead")
		

	@commands.command(pass_context=True)
	async def lastgame(self, ctx):
		""" Get your latest stats

		Just run:
		?lastgame
		"""
		userinfo = botdata.userinfo(ctx.message.author.id)
		if(userinfo.steam == ""):
			await self.bot.say("You need to add your Steam ID! Use the ?setsteam <steam_ID> command")
		else:
			await self.bot.send_typing(ctx.message.channel)
			await self.write_stats(userinfo)


def setup(bot):
	global d2api
	try:
		import dota2api
		d2api = dota2api.Initialise(settings.steamapikey)
	except:
		raise ModuleNotFound("Either dota2api isnt installed, or your steam api key is not valid")
	bot.add_cog(DotaStats(bot))
	