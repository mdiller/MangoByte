import discord
import asyncio
import string
import os
import sys
import json
import dota2api
import csv
import datetime
from gtts import gTTS
from discord.ext import commands
from ctypes.util import find_library

discord.opus.load_opus(find_library('opus'))

with open('settings.json') as settings_file:
	settings = json.load(settings_file)

d2api = dota2api.Initialise(settings['steamapikey'])

def findfile(name, path):
	for root, dirs, files in os.walk(path):
		if name in files:
			return os.path.join(root, name)
	return None

# gets a list of all the mp3s in the root resource directory
def get_playlist():
	clips = []
	for file in os.listdir(settings["resourcedir"]):
		if file.endswith(".mp3"):
			clips.append(os.path.splitext(file)[0])
	return clips

# tts an audio clip from a word
def make_temp_mp3(word):
	tts = gTTS(text=word, lang='en')
	tts.save(settings["resourcedir"] + "temp/temp.mp3")

class MangoCog:
	"""MangoByte: like a normal byte, but jucier"""

	def __init__(self, bot):
		self.bot = bot
		self.voice = None
		self.player = None
		self.voice_channel = None


	# whether or not the bot is currently talking
	def is_talking(self):
		return (self.player is not None) and (not self.player.is_done())

	# try to say an mp3, and if we arent in a voice channel, join the default one
	async def try_talking(self, mp3name, volume=0.6):
		if(self.voice is None):
			print("tried to talk while not in voice channel")
			await self.bot.say("not in voice channel m8")
			return

		if self.is_talking():
			# we have a player and its playing something
			print("interruption")
			try:
				await self.bot.say("I'm already talking, don't interrupt. rude.")
			except Exception as e:
				print("couldnt report interruption")
			finally:
				return

		try:
			self.player = self.voice.create_ffmpeg_player(mp3name)
			self.player.volume = volume
			self.player.start()
			print("playing: " + mp3name)
		except Exception as e:
			print(str(e))
			await self.bot.say("thats not valid input, silly.")
	
	async def dota_stats(self):
		while True:
			tmp_file = open("tmpfile", "w")
			writer = csv.writer(tmp_file)
			if (os.stat("players.csv").st_size != 0):
				player_file = open('players.csv', 'rt')
				reader = csv.reader(player_file)	
				for row in reader:
					hist = d2api.get_match_history(account_id=row[1])
					if(int(hist['matches'][0]['match_id']) != int(row[2])):
						row[2] = hist['matches'][0]['match_id']
					writer.writerow(row)	
				player_file.close()
				os.remove('players.csv')
				os.rename("tmpfile",'players.csv')
				tmp_file.close()
				await asyncio.sleep(60)
				player_file.close()
			else:
				# Player file is currently empty!
				tmp_file.close()
				await asyncio.sleep(60)

	async def write_stats(self, player : str):
		player_file = open('players.csv', 'rt')
		reader = csv.reader(player_file)
		for row in reader:
			if (row[0] == str(player)):
				game = d2api.get_match_details(int(row[2]))
				match_result = game['radiant_win']
				true_ID = int(row[1]) - 76561197960265728 
				my_name = d2api.get_player_summaries(int(row[1]))
				for count in range(0,len(game['players'])):
					if(int(game['players'][count]['account_id']) == true_ID):
						if (count < 5 and match_result is True) or (count >= 5 and match_result is False):
							await self.bot.say(str(my_name['players'][0]['personaname']) + " won a game as " + str(game['players'][count]['hero_name']) + " in " + str(datetime.timedelta(seconds=game['duration'])))
							await self.format_stats(game['players'][count])
						else:
							await self.bot.say(str(my_name['players'][0]['personaname']) + " lost a game as " + str(game['players'][count]['hero_name']) + " in " + str(datetime.timedelta(seconds=game['duration'])))
							await self.format_stats(game['players'][count])

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
	async def addstats(self, ctx, player : int):
		"""Adds a player to the stat tracker

         	Just provide your Steam ID:
	 	?stats <steam_id>
		"""
		player_val = {str(ctx.message.author):player}
		player_list = open('players.csv', 'r')
		reader = csv.reader(player_list)
		for row in reader:
			if (row[0] == str(ctx.message.author)):
				await self.bot.say( str(ctx.message.author) + " is already here! I don't need more of you!")
				player_list.close()
				return
		player_list.close()	
		player_file = open('players.csv', 'a')
		writer = csv.writer(player_file)	
		try:
			hist = d2api.get_match_history(player)
		except:
			await self.bot.say("You must enable Expose Public Match Data in your DotA 2 client")
			return
		writer.writerow( (str(ctx.message.author), player,hist['matches'][0]['match_id'],) )
		player_file.close()
		await self.bot.say( "I added " + str(ctx.message.author) + " to the list of players. NOW I'M WATCHING YOU")
		

	@commands.command(pass_context=True)
	async def stats(self, ctx):
		""" Get your latest stats

		Just run:
		?stats
		"""
		player_list = open('players.csv','r')
		reader = csv.reader(player_list)
		for row in reader:
			if (row[0] == str(ctx.message.author)):
				await self.write_stats(str(ctx.message.author))
				return
		await self.bot.say("You need to add your Steam ID! Use the ?addtats <steam_ID> command")

	@commands.command(pass_context=True)
	async def ping(self, ctx, count : int):
		"""Pings a number of times(within reason)

		Pings... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await self.bot.say("thats not enough pings. stahp trying to break me.")
			return
		if count > 21:
			await self.bot.say("thats too many pings. stahp trying to break me.")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "Ping "
		await self.bot.say(ping_string, tts=True)

	@commands.command(pass_context=True)
	async def dota(self, ctx, dota_response : str):
		"""Plays a dota response

		The format for input is the name of the sound.
		Some gooduns:
		?dota treant_move_20
		?dota troll_lose_03
		?dota timb_rare_01
		?dota slark_rare_02
		?dota drag_inthebag_01
		?dota bristle_inthebag_01
		?dota undying_gummy_vit_01
		?dota undying_gummy_vit_03
		?dota spir_move_26
		?dota beas_ability_animalsound_05
		?dota gyro_move_13

		Note: This command will eventually be improved substantially"""
		response_file = findfile(dota_response + ".mp3", settings["dotavpk"] + "sounds/vo/")
		if(response_file != None):
			await self.try_talking(response_file, volume=0.3)
		else:
			await self.bot.say("Not a valid dota response");

	@commands.command(pass_context=True)
	async def hello(self, ctx):
		"""Says hello

		WHAT MORE DO YOU NEED TO KNOW!?!?!? IS 'Says hello' REALLY NOT CLEAR ENOUGH FOR YOU!?!!11?!!?11!!?!??"""
		await self.try_talking(settings["resourcedir"] + 'hello.mp3')

	@commands.command(pass_context=True)
	async def play(self, ctx, clip : str):
		"""Plays an audio clip

		example:
		?play hello

		for a complete list of the available clips, try ?playlist"""
		if clip in get_playlist():
			await self.try_talking(settings["resourcedir"] +  clip + '.mp3')
		else:
			await self.bot.say("'" + clip + "' is not a valid clip. try ?playlist.")

	@commands.command(pass_context=True)
	async def playlist(self, ctx):
		"""Lists the audio clips available for the play command"""
		clips = get_playlist()
		message = "```"
		for clip in clips:
			message += clip + "\n"
		message += "```"
		await self.bot.say(message)

	@commands.command(pass_context=True)
	async def playurl(self, ctx, url : str):
		"""Plays an mp3 file at a url

		Make sure to use http, not https.
		One way to use this is to go to:
		http://people.oregonstate.edu/~dillerm/ResponsePlayer/
		Once there, find a good audio clip, right click on it, select copy url address, and do the thing."""
		await self.try_talking(url)

	@commands.command(pass_context=True)
	async def echo(self, ctx, *, message : str):
		"""Echo...

		I would hurl words into this darkness and wait for an echo, and if an echo sounded, no matter how faintly, I would send other words to tell, to march, to fight, to create a sense of the hunger for life that gnaws in us all"""
		await self.bot.say(message)

	@commands.command(pass_context=True, hidden=True)
	async def join(self, ctx, channel_id : str):
		appinfo = await self.bot.application_info()
		if(appinfo.owner.id == ctx.message.author.id):
			new_channel = self.bot.get_channel(channel_id)
			if(new_channel == None):
				print("attempted to join invalid channel: " + channel_id)
				return

			await self.voice.move_to(new_channel)
			print("joined channel: " + channel_id)
			self.voice_channel = self.bot.get_channel(channel_id)
		else:
			print("non-owner tried to use owner command")

	#function called when this event occurs
	async def on_voice_state_update(self, before, after):
		if self.voice_channel is None or after.voice_channel is None or before.voice_channel == after.voice_channel:
			# if the bot or the member are not in a voice channel, don't worry about checking that theyre equal
			return
		if after.voice_channel.id == self.voice_channel.id and before.voice_channel != after.voice_channel:
			print(after.name + " joined the channel")

			await asyncio.sleep(3)
			await self.try_talking(settings["resourcedir"] + 'helloits.mp3')
			tts = gTTS(text=after.name, lang='en-au')
			tts.save(settings["resourcedir"] + "temp/temp.mp3")
			while self.is_talking():
				await asyncio.sleep(0.1)

			await self.try_talking(settings["resourcedir"] + "temp/temp.mp3")
			



bot = commands.Bot(command_prefix='?', description="""a bot that does stuff 'n things""")
cog = MangoCog(bot)
bot.add_cog(cog)

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))
	print('Automatically connecting to default channel via ID...')
	cog.voice = await bot.join_voice_channel(bot.get_channel(settings['voicechannel']))
	cog.voice_channel = cog.voice.channel
	await cog.try_talking(settings["resourcedir"] + "bothello.mp3", volume=0.3)
	await cog.dota_stats()

@bot.event
async def on_command_error(error, ctx):
	if isinstance(error, commands.MissingRequiredArgument):
		await bot.send_message(ctx.message.channel,
				"need moar arguments on command ?{0} try doin ?help {0} to see how its done.".format(ctx.command))
	elif isinstance(error, commands.BadArgument):
		await bot.send_message(ctx.message.channel,
				"need better arguments on command ?{0} try doin ?help {0} to see how its done.".format(ctx.command))
	else:
		print("error executing command [" + ctx.command + "]: " + error)

token = settings['token']

bot.run(token)
