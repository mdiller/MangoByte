import discord
from discord.ext import commands
from .utils.settings import *
import asyncio
import string
import dota2api
import datetime


# returns the latest dota game played by the user
def dota_latest_game(userinfo):
	hist = d2api.get_match_history(account_id=userinfo.steam)
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
		true_ID = userinfo.steam - 76561197960265728 
		my_name = str(d2api.get_player_summaries(userinfo.steam)['players'][0]['personaname'])
		
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
		kills = game['kills']
		deaths = game['deaths']
		assists= game['assists']
		gpm = game['gold_per_min']
		deny = game['denies']
		damage = game['hero_damage']
		lh = game['last_hits']
		xpm = game['xp_per_min']
		spent = int(game['gold_spent']) + int(game['gold'])
		level = game['level']
		await self.bot.say("""
		```
		------------------------------------------------------------
		| KILLS: """ + str(kills) + """ | DEATHS: """ + str(deaths) + """ | ASSISTS: """ + str(assists) + """ | GPM: """ + str(gpm) + """ | XPM: """ + str(xpm) + """ |
		--------------------------------------------------------------------------------
		| NET WORTH: """ + str(spent) + """ | LAST HITS: """ + str(lh) + """ | DENIES: """ + str(deny) + """ | HERO DAMAGE: """ + str(damage) + """ | LEVEL: """ + str(level) + """ |
		--------------------------------------------------------------------------------
		```
		""")

	@commands.command(pass_context=True)
	async def addstats(self, ctx, steam_id : int):
		"""Adds a dota player to the dota stat tracker, vie their steam id
		
	 	To get your steam_id, an easy way is to go to your profile page in steam, right click anywhere, and select 'Copy Page URL.' Then paste that somewhere, and get the number at the end of the url. It should start with a 7 and be like 16 characters or something. Thats your steam_id. Now just do ?addstats <thenumber>.
		"""
		global settings
		for user in settings.userinfo:
			if (user.discord == str(ctx.message.author)):
				await self.bot.say( str(ctx.message.author) + " is already here! I don't need more of you!")
				return

		try:
			hist = d2api.get_match_history(steam_id)
		except Exception as e:
			print(e.message)
			await self.bot.say("Either you must enable Expose Public Match Data in your DotA 2 client, or that is an invalid ID")
			return
		add_user(str(ctx.message.author), steam_id, hist['matches'][0]['match_id'])
		settings = Settings()

		await self.bot.say( "I added " + str(ctx.message.author) + " to the list of players. NOW I'M WATCHING YOU")
		

	@commands.command(pass_context=True)
	async def stats(self, ctx):
		""" Get your latest stats

		Just run:
		?stats
		"""
		for user in settings.userinfo:
			if (user.discord == str(ctx.message.author)):
				await self.write_stats(user)
				return
		await self.bot.say("You need to add your Steam ID! Use the ?addtats <steam_ID> command")

def setup(bot):
	global d2api
	try:
		import dota2api
		d2api = dota2api.Initialise(settings.steamapikey)
	except:
		raise ModuleNotFound("Either dota2api isnt installed, or your steam api key is not valid")
	bot.add_cog(DotaStats(bot))
	