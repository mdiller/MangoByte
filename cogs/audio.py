import discord
from discord.ext import commands
from discord.ext.commands.bot import _get_variable
from cogs.utils.helpers import *
from cogs.utils.clip import *
from __main__ import settings, botdata
from cogs.utils import checks
import asyncio
import os
import string
import queue
import random
import re
import urllib.request
from random import randint
from .mangocog import *
from ctypes.util import find_library

discord.opus.load_opus(find_library('opus'))

def get_clipdirs():
	result = []
	for root, dirs, files in os.walk(settings.resourcedir + "clips/"):
		for d in dirs:
			result.append(d)
	result.sort()
	return result

# gets a list of all the mp3s in the indicated clipdir
def get_playlist(clipdir):
	clips = []
	for root, dirs, files in os.walk(settings.resourcedir + "clips/" + clipdir):
		for file in files:
			if file.endswith(".mp3"):
				clips.append(file[:-4])
	clips.sort()
	return clips

def remove_if_temp(mp3name):
	if os.path.isfile(mp3name):
		if os.path.dirname(mp3name) == os.path.join(settings.resourcedir, "temp"):
			os.remove(mp3name)
			print("removed temp file " + mp3name)


class AudioPlayer:
	"""The server-specific objects used for mangobyte's audio output"""
	def __init__(self, bot, server):
		self.bot = bot
		self.server = server
		self.voice = None
		self.player = None
		self.clipqueue = queue.Queue()
		self.last_clip = None

	@property
	def voice_channel(self):
		if self.voice is None:
			return None
		else:
			return self.server.me.voice_channel

	# connects to a voice channel
	async def connect(self, channel):
		if not isinstance(channel, discord.Channel):
			channel = self.bot.get_channel(channel)

		if self.voice is None:
			self.voice = await self.bot.join_voice_channel(channel)
		else:
			await self.voice.move_to(channel)

	def done_talking(self):
		self.player = None
		if not self.clipqueue.empty():
			self.play_next_clip()

	# gets the next clip from the clip queue
	def next_clip(self):
		if not self.clipqueue.empty():
			return self.clipqueue.get()
		raise ValueError("clip queue was empty when we tried to get the next one")

	# plays the next clip in the queue
	def play_next_clip(self):
		clip = self.next_clip()
		self.player = self.voice.create_ffmpeg_player(clip.audiopath, after=self.done_talking)
		self.player.volume = clip.volume
		self.player.start()
		print("playing: " + clip.audiopath)
		if self.last_clip != None and clip.audiopath != self.last_clip.audiopath:
			remove_if_temp(self.last_clip.audiopath)
		self.last_clip = clip

	# try queueing an mp3 to play
	async def queue_clip(self, clip):
		if(self.voice is None):
			print("tried to talk while not in voice channel")
			await self.bot.say("not in voice channel m8")
			return

		self.clipqueue.put(clip)

		if self.player is None or self.player.is_done():
			self.play_next_clip()



class Audio(MangoCog):
	"""Commands used to play audio"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.audioplayers = []

	# gets the audioplayer for the current server/channel
	async def audioplayer(self, server=None, error_on_none=True):
		# TODO: ACCOUNT FOR WHEN THIS MESSAGE IS A PM
		if server is None:
			channel = _get_variable('_internal_channel')
			if channel.type is discord.ChannelType.text:
				server = channel.server
			else:
				# This is likely a private message, so figure out if theres a server they could mean
				author = _get_variable('_internal_author')
				for audioplayer in self.audioplayers:
					member = audioplayer.server.get_member(author.id)
					if member is not None and audioplayer.voice_channel == member.voice_channel:
						if botdata.serverinfo(audioplayer.server).is_banned(member):
							raise UserError("Nice try, but you're banned in the voice channel that I'm in")
						return audioplayer

				raise UserError("You're not in any voice channels that I'm in")

		if isinstance(server, discord.Channel):
			server = server.server
		for audioplayer in self.audioplayers:
			if audioplayer.server == server:
				return audioplayer

		if error_on_none:
			raise UserError("I'm not in a voice channel on this server. Have an admin do `{}summon` to put me in one.".format(self.bot.command_prefix))
		else:
			return None

	# Connects an audioplayer for the correct server to the indicated channel
	async def connect_voice(self, channel):
		if not isinstance(channel, discord.Channel):
			channel = self.bot.get_channel(channel)

		audioplayer = await self.audioplayer(channel, error_on_none=False)
		if audioplayer is not None:
			await audioplayer.connect(channel)
		else:
			audioplayer = AudioPlayer(self.bot, channel.server)
			await audioplayer.connect(channel)
			self.audioplayers.append(audioplayer)
			clip = await self.get_clip("local:bothello")
			clip.volume = 0.1
			await self.play_clip(clip, channel)

	async def disconnect(self, server):
		audioplayer = await self.audioplayer(server)
		if audioplayer is not None:
			await audioplayer.voice.disconnect()
			self.audioplayers.remove(audioplayer)


	@commands.command(pass_context=True)
	async def play(self, ctx, clip : str=""):
		"""Plays an audio clip

		example:
		`{cmdpfx}play hello`

		for a complete list of the available clips, try `{cmdpfx}playlist`"""
		try:
			await self.play_clip("local:" + clip)
		except ClipNotFound:
			await self.bot.say("'" + clip + "' is not a valid clip. 🤦 Try ?playlist. ")
			

	@commands.command(pass_context=True)
	async def playlist(self, ctx, section : str=None):
		"""Lists the audio clips available for the play command

		Calling this command with no arguments gets you a list of sections and a list of all of the clips

		To get the clips in a specific section, do `{cmdpfx}playlist <section>`"""
		dirs = get_clipdirs()

		message = ""
		clips = []

		if section is None:
			message += "**Sections:**\n"
			for section in dirs:
				message += "`{}` ".format(section)
			message += "\n**Clips:**\n"
			for section in dirs:
				clips += get_playlist(section)
		elif section not in dirs:
			message +=("Dats not a valid section. You can choose from one of these:\n")
			for section in dirs:
				message += "`{}` ".format(section)
		else:
			clips = get_playlist(section)

		if len(clips) > 0:
			clips.sort()
			for clip in clips:
				message += "`{}` ".format(clip)

		await self.bot.say(message)

	@commands.command(pass_context=True)
	async def playurl(self, ctx, mp3url : str):
		"""Plays an mp3 file at a url

		Make sure to use http, not https"""
		await self.play_clip("url:" + mp3url)

	@commands.command(pass_context=True)
	async def stop(self, ctx):
		"""Stops the currently playing audio

		Also empties the clip queue
		"""
		audioplayer = await self.audioplayer()
		while not audioplayer.clipqueue.empty():
			try:
				audioplayer.clipqueue.get()
			except Empty:
				continue
		if not audioplayer.player is None:
			audioplayer.player.stop();

	@commands.command(pass_context=True)
	async def replay(self, ctx):
		"""Replays the last played clip
		"""
		last_clip = (await self.audioplayer()).last_clip
		if last_clip == None:
			await self.bot.say("Nobody said anythin' yet")
			return

		# If its not a temp file
		await self.bot.say("Replaying " + last_clip.clipid)
		await self.play_clip(last_clip)

	@commands.command(pass_context=True)
	async def clipinfo(self, ctx, clipid=None):
		"""Gets information and a file for the given clip

		Not giving a clipid will print info about the last clip played

		clipid is specified like this:
		`local:shitpickle`
		`dota:timb_ally_01`
		"""
		if clipid is None:
			if (await self.audioplayer()).last_clip == None:
				await self.bot.say("Nobody said anythin' yet")
				return
			clipid = (await self.audioplayer()).last_clip.clipid

		clip = await self.get_clip(clipid)

		await self.bot.send_typing(ctx.message.channel)

		filename = clip.name

		if re.search(r"[^a-zA-Z0-9_]", filename):
			filename = clip.type()

		filename += os.path.splitext(clip.audiopath)[1]

		try:
			await self.bot.send_file(ctx.message.channel, clip.audiopath, filename=filename, content=await clip.get_info())
		except FileNotFoundError as e:
			# The file is probably actually a url
			fp = urllib.request.urlopen(clip.audiopath)
			await self.bot.send_file(ctx.message.channel, fp, filename=filename, content=await clip.get_info())
			fp.close()



	@commands.command(pass_context=True)
	async def setintro(self, ctx, clipname : str=None, user: discord.User=None):
		"""Sets your intro clip

		Calling this command without a clipname will tell you your current intro

		The argument is the name of the clip that will introduce you, for example:
		`{cmdpfx}setintro math`
		**Note:** your intro clip cannot be longer than 4 seconds
		"""
		if user is None:
			user = ctx.message.author
		else:
			if not await checks.is_owner_check(ctx):
				await self.bot.say("You aint the boss of me 😠")
				return

		if clipname is None:
			intro = botdata.userinfo(user.id).intro
			if intro is None or intro == "":
				await self.bot.say("Yer intro isn't set. Try doin somethin' like `?setintro dota:gyro_items_01`")
				return
			else:
				await self.bot.say("Your intro is: {}".format(intro))
				await self.play_clip("tts:your intro is")
				await self.play_clip(intro)
				return

		clip = await self.get_clip_try_types(clipname, "local|dota")

		audiolength = clip.audiolength

		if audiolength > 3.0:
			await self.bot.say("Dat clip is " + str(audiolength) + " seconds long, and intros gotta be less than 3.")
			return

		botdata.userinfo(user.id).intro = clip.clipid
		await self.bot.say("Yer intro is now " + clip.clipid)


	@commands.command(pass_context=True)
	async def setoutro(self, ctx, clipname : str=None, user: discord.User=None):
		"""Sets your outro clip

		Calling this command without a clipname will tell you your current outro

		The argument is the name of the clip that will 'outroduce' you, for example:
		`{cmdpfx}setoutro math`
		**Note:** your outro clip cannot be longer than 4 seconds
		"""
		if user is None:
			user = ctx.message.author
		else:
			if not await checks.is_owner_check(ctx):
				await self.bot.say("You aint the boss of me 😠")
				return

		if clipname is None:
			outro = botdata.userinfo(user.id).outro
			if outro is None or outro == "":
				await self.bot.say("Yer outro isn't set. Try doin somethin' like `?setoutro dota:troll_lose_03`")
				return
			else:
				await self.bot.say("Your outro is: {}".format(outro))
				await self.play_clip("tts:your outro is")
				await self.play_clip(outro)
				return

		clip = await self.get_clip_try_types(clipname, "local|dota")

		audiolength = clip.audiolength

		if audiolength > 3.0:
			await self.bot.say("Dat clip is " + str(audiolength) + " seconds long, and outros gotta be less than 3.")
			return

		botdata.userinfo(user.id).outro = clip.clipid
		await self.bot.say("Yer outro is now " + clip.clipid)


	@commands.command(pass_context=True)
	async def tts(self, ctx, *, message : str):
		"""Like echo but for people who can't read

		...what more could you possibly need to know...
		"""
		gtts_fixes = read_json(settings.resourcedir + "ai/gtts_fixes.json")
		text = ctx.message.clean_content[5:]
		for key in gtts_fixes:
			text = re.sub("\\b({})\\b".format(key), gtts_fixes[key], text, re.IGNORECASE)
		await self.play_clip("tts:" + text)

	@commands.command(pass_context=True)
	async def later(self, ctx):
		"""Tells you how much later it is

		Theres 19 different ones"""
		await self.play_clip("local:later{}".format(randint(1,19)))


	@checks.is_admin()
	@commands.command(pass_context=True, hidden=True)
	async def summon(self, ctx):
		"""Summons the bot to the voice channel you are currently in
		(Requires administrator privilages)"""
		new_channel = ctx.message.author.voice.voice_channel
		if new_channel is None:
			raise UserError("You are not currently in a voice channel")
		if new_channel.server != ctx.message.server:
			raise UserError("You are not currently in a voice channel on this server")

		await self.connect_voice(new_channel)
		botdata.serverinfo(new_channel.server.id).voicechannel = new_channel.id

	@checks.is_admin()
	@checks.is_not_PM()
	@commands.command(pass_context=True, hidden=True)
	async def unsummon(self, ctx):
		"""Removes the bot from the voice channel it is currently in
		(Requires administrator privilages)"""
		await self.disconnect(ctx.message.server)
		botdata.serverinfo(ctx.message.server.id).voicechannel = None

	# fixes discord user names which either are in all caps or have a number serving as a letter
	async def fix_name(self, name):
		# If all upper case or numbers n stuff, make all lower case
		if re.match(r"^[^a-z]*$", name):
			name = name.lower()

		# Simple replacing of all numbers that appear to be acting as letters
		letternumbers = { "0": "o", "1": "i", "3": "e", "4": "a", "7": "t" }
		for num in letternumbers:
			name = re.sub("{}([A-Za-z])".format(num), r"{}\1".format(letternumbers[num]), name)
		return name

	#function called when this event occurs
	async def on_voice_state_update(self, before, after):
		if before.voice_channel == after.voice_channel:
			return # if the member didnt change channels, dont worry about it
		if before.voice_channel is not None:
			beforeplayer = await self.audioplayer(before.voice_channel, error_on_none=False)
			if beforeplayer is not None and beforeplayer.voice_channel == before.voice_channel:
				text = (await self.fix_name(before.name)) + " has left!"
				print(text)
				outroclip = "local:farewell"

				userinfo = botdata.userinfo(before.id)
				if userinfo.outro != "" and userinfo.outro != outroclip:
					outroclip = userinfo.outro

				await asyncio.sleep(0.5)
				await self.play_clip(outroclip, before.server)
				await self.play_clip("tts:" + text, before.server)
		if after.voice_channel is not None:
			afterplayer = await self.audioplayer(after.voice_channel, error_on_none=False)
			if afterplayer is not None and afterplayer.voice_channel == after.voice_channel:
				text = await self.fix_name(after.name)
				print(text + " joined the channel")
				introclip = "local:helloits"

				userinfo = botdata.userinfo(after.id)
				if userinfo.intro != "" and userinfo.intro != introclip:
					introclip = userinfo.intro
					text = "its " + after.name

				await asyncio.sleep(3)
				await self.play_clip(introclip, after.server)
				await self.play_clip("tts:" + text, after.server)


def setup(bot):
	bot.add_cog(Audio(bot))