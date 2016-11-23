import discord
from discord.ext import commands
from __main__ import settings, botdata
import asyncio
import string
import dota2api
import datetime


# returns the latest dota game played by the user
def dota_latest_game(userinfo):
	hist = d2api.get_match_history(account_id=int(userinfo.steam))
	return d2api.get_match_details(hist['matches'][0]['match_id'])

class DotaStats:
	"""Commands used to access Dota 2 players' stats
	"""

	def __init__(self, bot):
		self.bot = bot

	# prints the stats for the given player's latest game
	async def write_stats(self, userinfo):
		game = dota_latest_game(userinfo)
		match_result = game['radiant_win']
		true_ID = int(userinfo.steam) - 76561197960265728 
		my_name = str(d2api.get_player_summaries(int(userinfo.steam))['players'][0]['personaname'])
		
		for player in game['players']:
			if(int(player['account_id']) == true_ID):
				if (player['player_slot'] < 5 and match_result is True) or (player['player_slot'] >= 5 and match_result is False):
					await self.bot.say(my_name + " won a game as " + str(player['hero_name']) + " in " + str(datetime.timedelta(seconds=game['duration'])))
					await self.format_stats(player)
				else:
					await self.bot.say(my_name + " lost a game as " + str(player['hero_name']) + " in " + str(datetime.timedelta(seconds=game['duration'])))
					await self.format_stats(player)

	# prints the stats for the given player's game in a readable format
	async def format_stats(self, game : str):
		embed = discord.Embed()

		embed.add_field(name="Kills", value=game['kills'])
		embed.add_field(name="Deaths", value=game['deaths'])
		embed.add_field(name="Assists", value=game['assists'])
		embed.add_field(name="GPM", value=game['gold_per_min'])
		embed.add_field(name="Denies", value=game['denies'])
		embed.add_field(name="Hero Damage", value=game['hero_damage'])
		embed.add_field(name="Last Hits", value=game['last_hits'])
		embed.add_field(name="XPM", value=game['xp_per_min'])
		embed.add_field(name="Net Worth", value=int(game['gold_spent']) + int(game['gold']))
		embed.add_field(name="Level", value=game['level'])

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
	