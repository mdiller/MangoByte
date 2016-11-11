import discord
from discord.ext import commands
from __main__ import settings, botdata
import asyncio
import os
import string
import queue
from gtts import gTTS
from ctypes.util import find_library

discord.opus.load_opus(find_library('opus'))

# tts an audio clip from a word
def make_temp_mp3(word):
	tts = gTTS(text=word, lang='en')
	tts.save(settings.resourcedir + "temp/temp.mp3")

def get_clipdirs():
	result = []
	for root, dirs, files in os.walk(settings.resourcedir + "clips/"):
		for d in dirs:
			result.append(d)
	result.sort()
	return result

def get_clipfile(clipname):
	for root, dirs, files in os.walk(settings.resourcedir + "clips/"):
		for file in files:
			if(file == clipname + ".mp3"):
				return os.path.join(root, file)
	return None

# gets a list of all the mp3s in the indicated clipdir
def get_playlist(clipdir):
	clips = []
	for root, dirs, files in os.walk(settings.resourcedir + "clips/" + clipdir):
		for file in files:
			if file.endswith(".mp3"):
				clips.append(file[:-4])
	clips.sort()
	return clips

class Clip:
	def __init__(self, mp3name, volume):
		self.mp3name = mp3name
		self.volume = volume

class Audio:
	"""Commands used to play audio
	"""

	def __init__(self, bot):
		self.bot = bot
		self.voice = None
		self.player = None
		self.clipqueue = queue.Queue()
		self.last_clip = None


	# whether or not the bot is currently talking
	def is_talking(self):
		return (self.player is not None) and (not self.player.is_done())

	def done_talking(self):
		self.player = None
		if not self.clipqueue.empty():
			self.play_next_clip()

	# gets the next clip from the clip queue
	def next_clip(self):
		if not self.clipqueue.empty():
			return self.clipqueue.get()
		raise ValueError("clip queue was empty when we tried to get the next one")

	# puts a clip on the clipqueue
	async def queue_clip(self, clip):
		self.clipqueue.put(clip)

	# plays the next clip in the queue
	def play_next_clip(self):
		try:
			clip = self.next_clip()
			self.player = self.voice.create_ffmpeg_player(clip.mp3name, after=self.done_talking)
			self.player.volume = clip.volume
			self.player.start()
			print("playing: " + clip.mp3name)
			self.last_clip = clip
		except Exception as e:
			print(str(e))

	# try to say an mp3, and if we arent in a voice channel, join the default one
	async def try_talking(self, mp3name, volume=0.6):
		if(self.voice is None):
			print("tried to talk while not in voice channel")
			await self.bot.say("not in voice channel m8")
			return

		await self.queue_clip(Clip(mp3name, volume))

		if not self.is_talking():
			self.play_next_clip()

	@commands.command(pass_context=True)
	async def play(self, ctx, clip : str=""):
		"""Plays an audio clip

		example:
		?play hello

		for a complete list of the available clips, try ?playlist"""
		clipfile = get_clipfile(clip)
		if clipfile == None:
			await self.bot.say("'" + clip + "' is not a valid clip. try ?playlist.")
		else:
			await self.try_talking(clipfile)
			

	@commands.command(pass_context=True)
	async def playlist(self, ctx, section : str=""):
		"""Lists the audio clips available for the play command in the indicated section

		There were beginning to be too many clips so I made a sections system"""
		dirs = get_clipdirs()

		message = ""

		if ((not section in dirs) and section != ""):
			message +=("Thats not a valid section...\n")
			section = ""

		clips = get_playlist(section)
		if section == "":
			message += "Pick a section and do ?playlist <section>\n"
			message += "Sections:\n"
			for d in dirs:
				message += " - " + d + "\n"
		else:
			message += "```\n"
			for clip in clips:
				message += clip + "\n"
			message += "```"
		await self.bot.say(message)

	@commands.command(pass_context=True)
	async def playurl(self, ctx, mp3url : str):
		"""Plays an mp3 file at a url

		Make sure to use http, not https.
		One way to use this is to go to:
		http://dotabase.me/responses/
		Once there, find a good audio clip, right click on it, select copy url address, and do the thing."""
		await self.try_talking(mp3url)

	@commands.command(pass_context=True)
	async def stop(self, ctx):
		"""Stops the currently playing audio

		Also empties the clip queue
		"""
		while not self.clipqueue.empty():
			try:
				self.clipqueue.get()
			except Empty:
				continue
		if not self.player is None:
			self.player.stop();

	@commands.command(pass_context=True)
	async def replay(self, ctx):
		"""Replays the last played clip
		"""
		if self.last_clip == None:
			await self.bot.say("Nobody said anythin' yet")
			return
		await self.try_talking(self.last_clip.mp3name, self.last_clip.volume)

	# @commands.command(pass_context=True)
	# async def setintro(self, ctx, clipname : str):
	# 	"""Sets your intro clip

	# 	The argument is the name of the clip that will introduce you, for example:
	# 	?setintro math
	# 	Note: your intro clip cannot be longer than 3 seconds
	# 	"""
	# 	bot.say()

	#function called when this event occurs
	async def on_voice_state_update(self, before, after):
		if self.voice is None or after.voice_channel is None or before.voice_channel == after.voice_channel or before.voice_channel == after.voice_channel:
			# if the bot or the member are not in a voice channel, or if the member's channel didnt change, don't worry about checking that theyre equal
			return
		if after.voice_channel.id == self.voice.channel.id:
			print(after.name + " joined the channel")

			# id used because it doesnt contain strange characters like name does, and is unique to this user
			tempfilename = settings.resourcedir + "temp/nameof_" + after.id + ".mp3"

			text = after.name
			clipname = "helloits"

			userinfo = botdata.userinfo(after.id)
			if userinfo.intro != "":
				clipname = userinfo.intro
				text = "its " + after.name

			tts = gTTS(text=text, lang='en-au')
			tts.save(tempfilename)

			await asyncio.sleep(3)
			await self.try_talking(get_clipfile(clipname))
			await self.try_talking(tempfilename)


def setup(bot):
	bot.add_cog(Audio(bot))