import discord
from discord.ext import commands
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

class AudioPlayerNotFoundError(UserError):
	def __init__(self, message):
		self.message = message

def get_clipdirs():
	result = []
	for root, dirs, files in os.walk(settings.resource("clips/")):
		for d in dirs:
			result.append(d)
	result.sort()
	return result

# gets a list of all the mp3s in the indicated clipdir
def get_playlist(clipdir):
	clips = []
	for root, dirs, files in os.walk(settings.resource("clips/" + clipdir)):
		for file in files:
			if file.endswith(".mp3") or file.endswith(".wav"):
				clips.append(file[:-4])
	clips.sort()
	return clips

def remove_if_temp(mp3name):
	if os.path.isfile(mp3name):
		if os.path.dirname(mp3name) == settings.resource("temp"):
			os.remove(mp3name)
			print("removed temp file " + mp3name)


class AudioPlayer:
	"""The guild-specific objects used for mangobyte's audio output"""
	def __init__(self, bot, guild):
		self.bot = bot
		self.guild = guild
		self.player = None
		self.clipqueue = queue.Queue()
		self.last_clip = None

	@property
	def voice(self):
		return next((voice for voice in self.bot.voice_clients if voice.guild == self.guild), None)

	@property
	def voice_channel(self):
		if self.voice is None:
			return None
		else:
			return self.guild.me.voice_channel

	# connects to a voice channel
	async def connect(self, channel):
		if not isinstance(channel, discord.VoiceChannel):
			channel = self.bot.get_channel(channel)

		if self.voice is None:
			await channel.connect()
		else:
			await self.voice.move_to(channel)

	def done_talking(self, error):
		if error:
			print(f"Error on voice.play: {error.message}")
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
		self.voice.play(discord.FFmpegPCMAudio(clip.audiopath), after=lambda e: self.done_talking(e))
		self.voice.source = discord.PCMVolumeTransformer(self.voice.source)
		self.voice.source.volume = clip.volume
		print("playing: " + clip.audiopath)
		if self.last_clip != None and clip.audiopath != self.last_clip.audiopath:
			remove_if_temp(self.last_clip.audiopath)
		self.last_clip = clip

	# try queueing an mp3 to play
	async def queue_clip(self, clip):
		if(self.voice is None):
			print("tried to talk while not in voice channel")
			await ctx.channel.send("not in voice channel m8")
			return

		self.clipqueue.put(clip)

		if self.voice and not self.voice.is_playing():
			self.play_next_clip()



class Audio(MangoCog):
	"""For playing audio in a voice channel

	For dota-related audio commands, try `{cmdpfx}help dotabase`"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.audioplayers = []

	# gets the audioplayer for the current guild/channel/context
	async def audioplayer(self, ctx, error_on_none=True):
		# TODO: ACCOUNT FOR WHEN THIS MESSAGE IS A PM
		if isinstance(ctx, discord.ext.commands.Context):
			if ctx.message.guild is None: # This is a private channel, so give it user
				ctx = ctx.message.author
			else:
				ctx = ctx.message.guild

		if isinstance(ctx, discord.User):
			author = ctx
			for audioplayer in self.audioplayers:
				member = audioplayer.guild.get_member(author.id)
				if member is not None and audioplayer.voice_channel == member.voice_channel:
					if botdata.guildinfo(audioplayer.guild).is_banned(member):
						raise AudioPlayerNotFoundError("Nice try, but you're banned in the voice channel that I'm in")
					return audioplayer
			if error_on_none:
				raise AudioPlayerNotFoundError("You're not in any voice channels that I'm in")
			else:
				return None
		elif isinstance(ctx, discord.Guild):
			guild = ctx
		elif isinstance(ctx, discord.abc.GuildChannel):
			guild = ctx.guild
		else:
			raise ValueError(f"Incorrect type '{type(ctx)}' given to audioplayer function")

		for audioplayer in self.audioplayers:
			if audioplayer.guild == guild:
				return audioplayer

		if error_on_none:
			raise AudioPlayerNotFoundError(f"I'm not in a voice channel on this server/guild. Have an admin do `{self.bot.command_prefix}summon` to put me in one.")
		else:
			return None

	# Connects an audioplayer for the correct guild to the indicated channel
	async def connect_voice(self, channel):
		if not isinstance(channel, discord.abc.GuildChannel):
			channel = self.bot.get_channel(channel)
		if channel is None:
			raise UserError("channel not found")
			return

		audioplayer = await self.audioplayer(channel, error_on_none=False)
		if audioplayer is not None:
			await audioplayer.connect(channel)
		else:
			audioplayer = AudioPlayer(self.bot, channel.guild)
			await audioplayer.connect(channel)
			self.audioplayers.append(audioplayer)
			clip = await self.get_clip("local:bothello")
			clip.volume = 0.1
			await self.play_clip(clip, channel)

	async def disconnect(self, guild):
		audioplayer = await self.audioplayer(guild)
		if audioplayer is not None:
			await audioplayer.voice.disconnect()
			self.audioplayers.remove(audioplayer)

	@commands.command()
	async def play(self, ctx, *, clip : str):
		"""Plays an audio clip

		Example:
		`{cmdpfx}play hello`

		For a complete list of the available clips, try `{cmdpfx}playlist`

		This can also play other clip types via their ClipID
		Example:
		`{cmdpfx}play tts:hello there`"""
		if ":" not in clip:
			try:
				await self.play_clip(f"local:{clip}", ctx)
			except ClipNotFound:
				await ctx.channel.send(f"'{clip}' is not a valid clip. 🤦 Try ?playlist.")
		else:
			await self.play_clip(clip, ctx)

			

	@commands.command()
	async def playlist(self, ctx, section : str=None):
		"""Lists the audio clips available for the play command

		Calling this command with no arguments gets you a list of sections and a list of all of the clips

		To get the clips in a specific section, do `{cmdpfx}playlist <section>`

		You can also do `{cmdpfx}playlist new` to get the 10 newest clips"""
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
		elif section in [ "recent", "latest", "new" ]:
			clips = {}
			for root, dirs, files in os.walk(settings.resource("clips/")):
				for file in files:
					if file.endswith(".mp3") or file.endswith(".wav"):
						clips[file[:-4]] = os.path.getctime(os.path.join(root, file))
			clips = sorted(clips.items(), key=lambda x: x[1], reverse=True)
			for clip in clips[:10]:
				message += f"`{clip[0]}`\n"
			clips = []
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

		await ctx.channel.send(message)

	@commands.command()
	async def playurl(self, ctx, mp3url : str):
		"""Plays an mp3 file at a url

		Make sure to use http, not https"""
		await self.play_clip("url:" + mp3url, ctx)

	@commands.command()
	async def stop(self, ctx):
		"""Stops the currently playing audio

		Also empties the clip queue
		"""
		audioplayer = await self.audioplayer(ctx)
		while not audioplayer.clipqueue.empty():
			try:
				audioplayer.clipqueue.get()
			except Empty:
				continue
		if audioplayer.voice is not None:
			audioplayer.voice.stop()

	@commands.command()
	async def replay(self, ctx):
		"""Replays the last played clip
		"""
		last_clip = (await self.audioplayer(ctx)).last_clip
		if last_clip == None:
			await ctx.channel.send("Nobody said anythin' yet")
			return

		# If its not a temp file
		await ctx.channel.send("Replaying " + last_clip.clipid)
		await self.play_clip(last_clip, ctx)

	@commands.command()
	async def clipinfo(self, ctx, clipid=None):
		"""Gets information and a file for the given clip

		Not giving a clipid will print info about the last clip played

		clipid is specified like this:
		`local:shitpickle`
		`dota:timb_ally_01`
		"""
		if clipid is None:
			if (await self.audioplayer(ctx)).last_clip == None:
				await ctx.channel.send("Nobody said anythin' yet")
				return
			clipid = (await self.audioplayer(ctx)).last_clip.clipid

		try:
			clip = await self.get_clip(f"local:{clipid}")
		except ClipNotFound:
			clip = await self.get_clip(clipid)

		ctx.channel.typing()

		filename = clip.name

		if re.search(r"[^a-zA-Z0-9_]", filename):
			filename = clip.type()

		filename += os.path.splitext(clip.audiopath)[1]

		content = f"ClipID: **{clip.clipid}**"
		clip_info = await clip.get_info()
		if clip_info != "":
			content += f"\n\n{clip_info}"

		try:
			await ctx.channel.send(content, file=discord.File(clip.audiopath, filename=filename))
		except FileNotFoundError as e:
			# The file is probably actually a url
			fp = urllib.request.urlopen(clip.audiopath)
			await ctx.channel.send(content, file=discord.File(fp, filename=filename))
			fp.close()



	@commands.command()
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
			if not checks.is_owner_check(ctx.message.author):
				await ctx.channel.send("You aint the boss of me 😠")
				return

		if clipname is None:
			intro = botdata.userinfo(user.id).intro
			if intro is None or intro == "":
				await ctx.channel.send("Yer intro isn't set. Try doin somethin' like `?setintro dota:gyro_items_01`")
				return
			else:
				await ctx.channel.send("Your intro is: {}".format(intro))
				await self.play_clip("tts:your intro is", ctx)
				await self.play_clip(intro, ctx)
				return

		clip = await self.get_clip_try_types(clipname, "local|dota")

		audiolength = clip.audiolength

		if audiolength > 3.0:
			await ctx.channel.send("Dat clip is " + str(audiolength) + " seconds long, and intros gotta be less than 3.")
			return

		botdata.userinfo(user.id).intro = clip.clipid
		await ctx.channel.send("Yer intro is now " + clip.clipid)


	@commands.command()
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
			if not checks.is_owner_check(ctx.message.author):
				await ctx.channel.send("You aint the boss of me 😠")
				return

		if clipname is None:
			outro = botdata.userinfo(user.id).outro
			if outro is None or outro == "":
				await ctx.channel.send("Yer outro isn't set. Try doin somethin' like `?setoutro dota:troll_lose_03`")
				return
			else:
				await ctx.channel.send("Your outro is: {}".format(outro))
				await self.play_clip("tts:your outro is", ctx)
				await self.play_clip(outro, ctx)
				return

		clip = await self.get_clip_try_types(clipname, "local|dota")

		audiolength = clip.audiolength

		if audiolength > 3.0:
			await ctx.channel.send("Dat clip is " + str(audiolength) + " seconds long, and outros gotta be less than 3.")
			return

		botdata.userinfo(user.id).outro = clip.clipid
		await ctx.channel.send("Yer outro is now " + clip.clipid)


	@commands.command()
	async def tts(self, ctx, *, message : str):
		"""Like echo but for people who can't read

		Talks in whatever voice channel mangobyte is currently in
		
		Example:
		`{cmdpfx}tts Hello I'm a bot`
		"""
		await self.do_tts(ctx.message.clean_content[5:], ctx)


	async def do_tts(self, text, ctx):
		gtts_fixes = read_json(settings.resource("json/gtts_fixes.json"))
		text = text.replace("\n", " ")
		for key in gtts_fixes:
			text = re.sub("\\b({})\\b".format(key), gtts_fixes[key], text, re.IGNORECASE)
		await self.play_clip("tts:" + text, ctx)


	@commands.command()
	async def ttsclip(self, ctx, *, clip : str):
		"""Tries to text-to-speech the given clip

		Only works on clips that have text specified

		Example:
		`{cmdpfx}ttsclip yodel`
		"""
		if ":" not in clip:
			try:
				clip = await self.get_clip(f"local:{clip}")
			except ClipNotFound:
				await ctx.channel.send(f"'{clip}' is not a valid clip. 🤦 Try ?playlist.")
				return
		else:
			clip = await self.get_clip(clip)
		text = clip.text.lower()
		if text == "":
			await ctx.channel.send(f"I can't read this clip for tts 😕. Try a different one.")
			return

		await self.play_clip(f"tts:{text}", ctx)

	@commands.command(aliases= [ "stts" ])
	async def smarttts(self, ctx, *, message : str):
		"""Automatically find the best fit for the tts given

		First checks local clips (like `{cmdpfx}play`),
		Then checks if there is an exact match for a dota response clip,
		And if none of the above is found, does a simple tts clip"""
		await self.do_smarttts(message, ctx)

	async def do_smarttts(self, message, ctx):
		if message == "" or not message:
			return # dont say anything if theres nothin to be said
		try:
			await self.play_clip(f"local:{message}", ctx)
			return # Clip played successfully so we're done
		except ClipNotFound:
			pass
		dotabase = self.bot.get_cog("Dotabase")
		if dotabase:
			query = await dotabase.smart_dota_query(message.split(" "), [], exact=True)
			if query:
				await dotabase.play_response_query(query, ctx)
				return
		await self.do_tts(message, ctx)


	@checks.is_admin()
	@commands.command(hidden=True)
	async def ttschannel(self, ctx, channel : discord.abc.GuildChannel):
		"""Sets a channel as the "TTS Channel"
		*admin-only command*
		If someone types in this channel, mangobyte will automatically interpret it as a `{cmdpfx}smarttts` command

		**Example:** (If your channel name is tts)
		`{cmdpfx}ttschannel #tts`
		"""
		if channel.type != discord.ChannelType.text:
			await ctx.channel.send("You've gotta give me a text channel")
			return
		botdata.guildinfo(channel.guild.id).ttschannel = channel.id
		await ctx.channel.send(f"{channel.mention} has been set as the tts channel!")

	@checks.is_admin()
	@commands.command(hidden=True)
	async def unttschannel(self, ctx):
		"""Un-sets the "TTS Channel"
		*admin-only command*
		See `{cmdpfx}ttschannel` for more info on what this is about
		"""
		if not botdata.guildinfo(ctx.message.guild.id).ttschannel:
			await ctx.channel.send("TTS Channel has not been set. Try `?ttschannel <name of channel>`")
			return
		botdata.guildinfo(ctx.message.guild.id).ttschannel = None
		await ctx.channel.send("TTS Channel removed")

	async def on_message(self, message):
		if message.guild and (not message.content.startswith("?")) and message.author.id != self.bot.user.id:
			if botdata.guildinfo(message.guild).is_banned(message.author):
				return # banned users cant talk
			ttschannel = botdata.guildinfo(message.guild.id).ttschannel
			if ttschannel == message.channel.id:
				await self.do_smarttts(message.content, message.guild)


	@commands.command()
	async def later(self, ctx):
		"""Tells you how much later it is

		Theres 19 different ones"""
		await self.play_clip("local:later{}".format(randint(1,19)), ctx)


	@checks.is_admin()
	@commands.command(hidden=True)
	async def summon(self, ctx):
		"""Summons the bot to the voice channel you are currently in
		(Requires administrator privilages)"""
		new_channel = ctx.message.author.voice.channel
		if new_channel is None:
			raise UserError("You are not currently in a voice channel")
		if new_channel.guild != ctx.message.guild:
			raise UserError("You are not currently in a voice channel on this server/guild")

		await self.connect_voice(new_channel)
		botdata.guildinfo(new_channel.guild.id).voicechannel = new_channel.id

	@checks.is_admin()
	@checks.is_not_PM()
	@commands.command(hidden=True)
	async def unsummon(self, ctx):
		"""Removes the bot from the voice channel it is currently in
		(Requires administrator privilages)"""
		await self.disconnect(ctx.message.guild)
		botdata.guildinfo(ctx.message.guild.id).voicechannel = None

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
	async def on_voice_state_update(self, member, before, after):
		if before == after:
			return # if the member didnt change channels, dont worry about it
		if before and before.channel:
			beforeplayer = await self.audioplayer(before.channel, error_on_none=False)
			if beforeplayer is not None and beforeplayer.voice.channel.id == before.channel.id:
				text = (await self.fix_name(member.name)) + " has left!"
				print(text)
				outroclip = "local:farewell"

				userinfo = botdata.userinfo(member.id)
				if userinfo.outro != "" and userinfo.outro != outroclip:
					outroclip = userinfo.outro

				await asyncio.sleep(0.5)
				await self.play_clip(outroclip, before.channel)
				await self.play_clip("tts:" + text, before.channel)
		if after and after.channel:
			afterplayer = await self.audioplayer(after.channel, error_on_none=False)
			if afterplayer is not None and afterplayer.voice.channel.id == after.channel.id:
				if member.id == self.bot.user.id:
					botdata.guildinfo(after.channel.guild.id).voicechannel = after.channel.id

				text = await self.fix_name(member.name)
				print(text + " joined the channel")
				introclip = "local:helloits"

				userinfo = botdata.userinfo(member.id)
				if userinfo.intro != "" and userinfo.intro != introclip:
					introclip = userinfo.intro
					text = "its " + text

				await asyncio.sleep(3)
				await self.play_clip(introclip, after.channel)
				await self.play_clip("tts:" + text, after.channel)


def setup(bot):
	bot.add_cog(Audio(bot))