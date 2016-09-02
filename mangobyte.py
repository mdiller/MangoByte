import discord
import asyncio
import string
import os
import sys
import json
from gtts import gTTS
from discord.ext import commands
from ctypes.util import find_library

discord.opus.load_opus(find_library('opus'))

with open('settings.json') as settings_file:
    settings = json.load(settings_file)


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


	@commands.command(pass_context=True)
	async def ping(self, ctx, count : int):
		"""Pings a number of times(within reason)

		Pings... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await self.bot.say("thats not enough pings. stahp trying to break me.")
			return
		if count > 99:
			await self.bot.say("thats too many pings. stahp trying to break me.")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "Ping "
		await self.bot.say(ping_string, tts=True)

	@commands.command(pass_context=True)
	async def dota(self, ctx, dota_response : str):
		"""Plays a dota response

		The format for input is the end of a dota2 gamepedia url.
		Some gooduns:
		?dota /1/17/Treant_move_20
		?dota /3/3b/Troll_lose_03
		?dota /1/10/Timb_rare_01
		?dota /f/f1/Slark_rare_02
		?dota /e/e0/Drag_inthebag_01
		?dota /b/b7/Bristle_inthebag_01
		?dota /9/9d/Undying_gummy_vit_01
		?dota /b/b5/Undying_gummy_vit_03
		?dota /a/af/Spir_move_26
		?dota /4/43/Beas_ability_animalsound_05
		?dota /3/31/Gyro_move_13

		Note: This command will eventually be improved substantially"""
		await self.try_talking('http://hydra-media.cursecdn.com/dota2.gamepedia.com' + dota_response + '.mp3', volume=0.3)

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
		await bot.say(message)

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

@bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.MissingRequiredArgument):
        await bot.send_message(ctx.message.channel,
                "need moar arguments on command ?{0} try doin ?help {0} to see how its done.".format(ctx.command))
    elif isinstance(error, commands.BadArgument):
        await bot.send_message(ctx.message.channel,
                "need better arguments on command ?{0} try doin ?help {0} to see how its done.".format(ctx.command))

token = settings['token']

bot.run(token)
