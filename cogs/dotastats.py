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
		hist = d2api.get_match_history(account_id=int(userinfo.steam))
		game = d2api.get_match_details(hist['matches'][0]['match_id'])
		playerinfo = d2api.get_player_summaries(int(userinfo.steam))['players'][0]

		# Finds the player in the game which has our matching steam32 id
		player = next(p for p in game['players'] if int(p['account_id']) == userinfo.steam32)

		if player is None:
			raise ValueError("wtf hes not in is own game")

		won_game = (player['player_slot'] < 5 and game['radiant_win'] is True) or (player['player_slot'] >= 5 and game['radiant_win'] is False)

		embed = discord.Embed(description="{} a game as {} in {}".format(("Won" if won_game else "Lost"), player['hero_name'], datetime.timedelta(seconds=game['duration'])))

		embed.set_author(name=playerinfo['personaname'], icon_url=playerinfo['avatar'])
		embed.add_field(name="Kills", value=player['kills'], inline=True)
		embed.add_field(name="Deaths", value=player['deaths'], inline=True)
		embed.add_field(name="Assists", value=player['assists'])
		embed.add_field(name="GPM", value=player['gold_per_min'])
		embed.add_field(name="Denies", value=player['denies'])
		embed.add_field(name="Hero Damage", value=player['hero_damage'])
		embed.add_field(name="Last Hits", value=player['last_hits'])
		embed.add_field(name="XPM", value=player['xp_per_min'])
		embed.add_field(name="Net Worth", value=int(player['gold_spent']) + int(player['gold']))
		embed.add_field(name="Level", value=player['level'])

		await self.bot.say(embed=embed)


	@commands.command(pass_context=True)
	async def addstats(self, ctx, steam_id : int):
		"""Adds a dota player to the dota stat tracker, vie their steam id
		
		To get your steam_id, an easy way is to go to your profile page in steam, right click anywhere, and select 'Copy Page URL.' Then paste that somewhere, and get the number at the end of the url. It should start with a 7 and be like 16 characters or something. Thats your steam_id. Now just do ?addstats <thenumber>.
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
		

	@commands.command(pass_context=True)
	async def stats(self, ctx):
		""" Get your latest stats

		Just run:
		?stats
		"""
		userinfo = botdata.userinfo(ctx.message.author.id)
		if(userinfo.steam == ""):
			await self.bot.say("You need to add your Steam ID! Use the ?addtats <steam_ID> command")
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
	