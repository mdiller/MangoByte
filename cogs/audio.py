import discord
from discord.ext import commands
from cogs.utils.helpers import *
from cogs.utils.clip import *
from __main__ import settings, botdata, report_error, loggingdb
from cogs.utils import checks
import cogs.utils.botdatatypes as botdatatypes
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

intro_outro_length = 4.5

class TtsChannelError(Exception):
	def __init__(self, error):
		self.message = "Errored in the tts channel"
		self.original = error

class AudioPlayerNotFoundError(UserError):
	def __init__(self, message):
		super().__init__(message)

def remove_if_temp(mp3name):
	if os.path.isfile(mp3name):
		if os.path.dirname(mp3name) == settings.resource("temp"):
			os.remove(mp3name)
			print("removed temp file " + mp3name)


class AudioPlayer:
	"""The guild-specific objects used for mangobyte's audio output"""
	def __init__(self, bot, guild):
		self.bot = bot
		self.guild_id = guild.id
		self.guild = guild
		self.player = None
		self.clipqueue = queue.Queue()
		self.last_clip = None

	@property
	def voice(self):
		return self.guild.voice_client

	@property
	def voice_channel(self):
		if self.voice is None:
			return None
		else:
			return self.voice.channel

	async def update_guild(self):
		self.guild = await self.bot.fetch_guild(self.guild.id)

	# connects to a voice channel
	async def connect(self, channel):
		if not isinstance(channel, discord.VoiceChannel):
			channel = self.bot.get_channel(channel)

		voice = self.voice

		if voice is None:
			print(f"attempting connect to: {channel.id}")
			await channel.connect()
			print(f"finished connect to: {channel.id}")
		elif voice.channel and voice.channel.id == channel.id:
			print(f"doin a disconnect and reconnect for: {channel.id}")
			await voice.disconnect(force=True)
			await asyncio.sleep(1)
			await channel.connect()
			print(f"finished reconnect for: {channel.id}")
			# print(f"leaving this because we're supposedly already connected? ({channel.id})")
		else:
			print(f"attempting move to: {channel.id}")
			await voice.move_to(channel)
			print(f"finished move to: {channel.id}")

	def done_talking(self, error):
		if error:
			print(f"Error on voice.play: {error.message}")
		if not self.clipqueue.empty():
			coro = self.play_next_clip()
			fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
			try:
				fut.result()
			except:
				print(f"Error playing next clip")
				pass

	# gets the next clip from the clip queue
	def next_clip(self):
		if not self.clipqueue.empty():
			return self.clipqueue.get()
		raise ValueError("clip queue was empty when we tried to get the next one")

	# plays the next clip in the queue
	async def play_next_clip(self):
		clip = self.next_clip()

		try:
			self.voice.play(discord.FFmpegPCMAudio(clip.audiopath), after=self.done_talking)
		except discord.errors.ClientException as e:
			if str(e) == "Not connected to voice.":
				raise UserError("Error playing clip. Try doing `?resummon`.")
			else:
				raise

		self.voice.source = discord.PCMVolumeTransformer(self.voice.source)
		self.voice.source.volume = clip.volume
		print("playing: " + clip.audiopath)
		if self.last_clip != None and clip.audiopath != self.last_clip.audiopath:
			remove_if_temp(self.last_clip.audiopath)
		self.last_clip = clip

	# try queueing an mp3 to play
	async def queue_clip(self, clip, ctx):
		if(self.voice is None):
			print("tried to talk while not in voice channel")
			raise UserError("not in voice channel m8")

		self.clipqueue.put(clip)

		if self.voice and not self.voice.is_playing():
			await self.play_next_clip()



class Audio(MangoCog):
	"""For playing audio in a voice channel

	For dota-related audio commands, try `{cmdpfx}help dotabase`"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.audioplayers = []
		self.local_clipinfo = self.init_local_clipinfo()

	def init_local_clipinfo(self):
		infofile = settings.resource("clips/clipinfo.json")
		if os.path.isfile(infofile):
			clipinfos = read_json(infofile)
		else:
			clipinfos = {}
		clipsdir = settings.resource("clips/")
		for root, dirs, files in os.walk(clipsdir):
			for file in files:
				match = re.search(f"clips[/\\\\]((?:.*[/\\\\])?([^/\\\\]+)\.(?:{audio_extensions}))", os.path.join(root, file))
				if match:
					path = match.group(1)
					name = match.group(2)
					if name not in clipinfos:
						found = False
						for clipname in clipinfos:
							if clipinfos[clipname]["path"] == path:
								found = True
								break
						if not found:
							info = { "path": path }
							in_dir = re.search(f"(.+)[/\\\\](?:.+)\.(?:{audio_extensions})", path)
							if in_dir:
								info["tags"] = in_dir.group(1)
							clipinfos[name] = info

		write_json(infofile, clipinfos)
		return clipinfos

	def save_local_clipinfo(self):
		infofile = settings.resource("clips/clipinfo.json")
		write_json(infofile, self.local_clipinfo)


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
				if member and member.voice and audioplayer.voice and audioplayer.voice.channel.id == member.voice.channel.id:
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
			raise AudioPlayerNotFoundError(f"I'm not in a voice channel on this server/guild. Have an admin do `{botdata.command_prefix(ctx)}summon` to put me in one.")
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
			await audioplayer.update_guild()
			await audioplayer.connect(channel)
		else:
			audioplayer = AudioPlayer(self.bot, channel.guild)
			await audioplayer.connect(channel)
			self.audioplayers.append(audioplayer)

	async def disconnect(self, guild):
		audioplayer = await self.audioplayer(guild, False)
		if audioplayer is not None:
			if audioplayer.voice is not None:
				await audioplayer.voice.disconnect(force=True)
			self.audioplayers.remove(audioplayer)
		elif guild.me and guild.me.voice:
			voice = next((voice for voice in self.bot.voice_clients if voice.guild == guild), None)
			if voice:
				await voice.disconnect(force=True)


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
				dotabase = self.bot.get_cog("Dotabase")
				if dotabase:
					chat_clip = dotabase.get_chatwheel_sound_clip(clip)
					if chat_clip:
						await self.play_clip(chat_clip, ctx)
						return
				await ctx.send(f"'{clip}' is not a valid clip. 🤦 Try {self.cmdpfx(ctx)}playlist.")
		else:
			await self.play_clip(clip, ctx)

			

	@commands.command(aliases=["playlist"])
	async def clips(self, ctx, tag : str=None):
		"""Lists the local audio clips available for the play command

		Calling this command with no arguments gets you a list of all of the clips

		To get the clips that have a specific tag, do `{cmdpfx}clips <tag>`

		To get a list of all of the possible clip tags, try `{cmdpfx}clips tags`

		You can also do `{cmdpfx}clips new` to get the 10 newest clips"""
		message = ""
		clips = []
		sort = True

		if tag is None:
			message += "\n**Clips:**\n"
			for clipname in self.local_clipinfo:
				clips.append(clipname)
		elif tag in [ "recent", "latest", "new" ]:
			clips = {}
			for clipname in self.local_clipinfo:
				clips[clipname] = os.path.getctime(settings.resource(f"clips/{self.local_clipinfo[clipname]['path']}"))
			clips = list(map(lambda x: x[0], sorted(clips.items(), key=lambda x: x[1], reverse=True)))
			clips = clips[:10]
			sort = False
		elif tag in [ "tags", "sections" ]:
			message += "\n**Tags:**\n"
			for clipname in self.local_clipinfo:
				tags = self.local_clipinfo[clipname].get("tags")
				if tags:
					tags = tags.split("|")
					for t in tags:
						if t not in clips:
							clips.append(t)
		else:
			for clipname in self.local_clipinfo:
				info = self.local_clipinfo[clipname]
				tags = info.get("tags")
				if tags:
					tags = tags.split("|")
					if tag in tags:
						clips.append(clipname)
						continue
				if len(tag) > 3 and tag.lower() in info.get("author", "").lower():
					clips.append(clipname)
			if not clips:
				raise UserError("No clips not found for that tag")

		if len(clips) > 0:
			if sort:
				clips.sort()
			clip_format = "`{}` "
			if len(clips) <= 10:
				clip_format = "`{}`\n"
			for clip in clips:
				message += clip_format.format(clip)
		await ctx.send(message)

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
			await ctx.send("Nobody said anythin' yet")
			return

		# If its not a temp file
		await ctx.send("Replaying " + last_clip.clipid)
		await self.play_clip(last_clip, ctx)

	@commands.command()
	async def clipinfo(self, ctx, clipid=None):
		"""Gets information and a file for the given clip

		Not giving a clipid will print info about the last clip played

		clipid is specified like this:
		`local:shitpickle`
		`dota:shredder_timb_ally_01`
		"""
		if clipid is None:
			if (await self.audioplayer(ctx)).last_clip == None:
				await ctx.send("Nobody said anythin' yet")
				return
			clipid = (await self.audioplayer(ctx)).last_clip.clipid

		try:
			clip = await self.get_clip(f"local:{clipid}", ctx)
		except ClipNotFound:
			clip = await self.get_clip(clipid, ctx)

		await ctx.channel.trigger_typing()

		if clip.type() == "url":
			filename = clip.name.split("/")[-1]
		else:
			filename = clip.name

		filename = re.sub(r"[^a-zA-Z0-9]", "", filename)

		if filename == "" or len(filename) > 32:
			filename = clip.type()

		filename += os.path.splitext(clip.audiopath)[1]

		content = f"ClipID: **{clip.clipid}**"
		clip_info_embed = await clip.get_info_embed()
		# if clip_info != "":
		# 	content += f"\n\n{clip_info}"

		await ctx.send(embed=clip_info_embed)

		try:
			await ctx.send(file=discord.File(clip.audiopath, filename=filename))
		except FileNotFoundError as e:
			# The file is probably actually a url
			fp = urllib.request.urlopen(clip.audiopath)
			await ctx.send(file=discord.File(fp, filename=filename))
			fp.close()

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
			pattern = f"\\b({key})\\b" if not key.startswith("regex:") else re.sub("^regex:", "", key)
			text = re.sub(pattern, gtts_fixes[key], text, re.IGNORECASE)
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
				clip = await self.get_clip(f"local:{clip}", ctx)
			except ClipNotFound:
				await ctx.send(f"'{clip}' is not a valid clip. 🤦 Try `{self.cmdpfx(ctx)}playlist`")
				return
		else:
			clip = await self.get_clip(clip, ctx)
		text = clip.text.lower()
		if text == "":
			await ctx.send(f"I can't read this clip for tts 😕. Try a different one.")
			return

		await self.play_clip(f"tts:{text}", ctx)

	@commands.command(aliases= [ "stts" ])
	async def smarttts(self, ctx, *, message : str):
		"""Automatically find the best fit for the tts given

		First checks local clips (like `{cmdpfx}play`), then checks to see if it is an audio url, then checks if it's a dota chatwheel message, then checks if there is an exact match for a dota response clip, and if none of the above is found, does a simple tts clip"""
		await self.do_smarttts(message, ctx)

	async def do_smarttts(self, message, ctx):
		if message == "" or not message:
			return # dont say anything if theres nothin to be said
		simple_message = re.sub(r'[^a-z0-9\s_]', r'', message.lower())
		try:
			await self.play_clip(f"local:{simple_message}", ctx)
			return # Clip played successfully so we're done
		except ClipNotFound:
			pass
		if re.match(f'^https?://.*\.({audio_extensions})$', message):
			await self.play_clip(f"url:{message}", ctx)
			return
		dotabase = self.bot.get_cog("Dotabase")
		if dotabase:
			if simple_message in [ "haha", "lol" ]:
				await dotabase.hero_keyphrase_command(";laugh", None, ctx)
				return

			clip = dotabase.get_chatwheel_sound_clip(message)
			if clip:
				await self.play_clip(clip, ctx)
				return
			query = await dotabase.smart_dota_query(message.split(" "), [], exact=True)
			if query:
				await dotabase.play_response_query(query, ctx)
				return

		for clipname in self.local_clipinfo:
			clip = self.local_clipinfo[clipname]
			simple_text = re.sub(r'[^a-z0-9\s_]', r'', clip.get("text", "").lower())
			if simple_text == "":
				continue
			if simple_message == simple_text:
				await self.play_clip(f"local:{clipname}", ctx)
				return

		await self.do_tts(message, ctx)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild and (not message.content.startswith(self.cmdpfx(message.guild))) and message.author.id != self.bot.user.id:
			guildinfo = botdata.guildinfo(message.guild)
			if guildinfo.is_banned(message.author):
				return # banned users cant talk
			ttschannel = guildinfo.ttschannel
			if ttschannel == message.channel.id:
				if message.content.startswith("//") or message.content.startswith("#"):
					return # commented out stuff should be ignored
				await loggingdb.insert_message(message, "smarttts")
				try:
					if guildinfo.announcetts:
						name = message.author.name
						if guildinfo.usenickname and message.author.nick:
							name = message.author.nick
						name = await self.fix_name(name)
						await self.do_tts(f"{name} says", message.guild)
					await self.do_smarttts(message.clean_content, message.guild)
				except UserError as e:
					try:
						await message.channel.send(e.message)
					except discord.errors.Forbidden as e:
						print("on_message usererror blocked because permissions")
						pass
				except Exception as e:
					try:
						await message.channel.send("Uh-oh, sumthin dun gone wrong 😱")
					except discord.errors.Forbidden as e:
						print("on_message usererror blocked because permissions")
						pass
					await report_error(message, TtsChannelError(e))


	@commands.command()
	async def later(self, ctx):
		"""Tells you how much later it is

		Theres 19 different ones"""
		await self.play_clip("local:later{}".format(randint(1,19)), ctx)

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
	@commands.Cog.listener()
	async def on_voice_state_update(self, member, before, after):
		channel_id = "not sure yet"
		try:
			if member.bot and member.id != self.bot.user.id:
				return # ignore bots except for mahself
			if before and after and before.channel == after.channel:
				return # if the member didnt change channels, dont worry about it
			if before and before.channel and botdata.guildinfo(before.channel.guild).outros:
				beforeplayer = await self.audioplayer(before.channel, error_on_none=False)
				if beforeplayer is not None and beforeplayer.voice is not None and beforeplayer.voice.channel.id == before.channel.id:
					ctx = before.channel.guild
					guildinfo = botdata.guildinfo(before.channel.guild)
					userinfo = botdata.userinfo(member.id)
					channel_id = before.channel.id

					if member.id == self.bot.user.id:
						return # dont play outros for self, thatd be a bug

					try:
						outroclip = userinfo.outro
						if outroclip:
							outroclip = await self.get_clip(userinfo.outro, ctx)
							if outroclip.audiolength > botdatatypes.max_intro_outro_length + 0.5:
								userinfo.set_default(ctx, "outro")
								outroclip = userinfo.outro
					except:
						userinfo.set_default(ctx, "outro")
						outroclip = userinfo.outro

					outrotts = userinfo.outrotts
					name = member.name
					if guildinfo.usenickname and member.nick:
						name = member.nick


					text = (await self.fix_name(name)) + " " + outrotts
					print(text)

					await asyncio.sleep(0.5)
					if not outroclip is None:				
						await self.play_clip(outroclip, before.channel)
					await self.play_clip("tts:" + text, before.channel)
			if after and after.channel and botdata.guildinfo(after.channel.guild).intros:
				afterplayer = await self.audioplayer(after.channel, error_on_none=False)
				if afterplayer is not None and afterplayer.voice is not None and afterplayer.voice.channel.id == after.channel.id:
					ctx = after.channel.guild
					guildinfo = botdata.guildinfo(after.channel.guild)
					channel_id = after.channel.id
					if member.id == self.bot.user.id:
						guildinfo.voicechannel = after.channel.id
						return # dont play intros for self.

					userinfo = botdata.userinfo(member.id)

					try:
						introclip = userinfo.intro
						if introclip:
							introclip = await self.get_clip(userinfo.intro, ctx)
							if introclip.audiolength > botdatatypes.max_intro_outro_length + 0.5:
								userinfo.set_default(ctx, "intro")
								introclip = userinfo.intro
					except:
						userinfo.set_default(ctx, "intro")
						introclip = userinfo.intro

					introtts = userinfo.introtts
					name = member.name
					if guildinfo.usenickname and member.nick:
						name = member.nick

					# Special case for default
					if userinfo.intro == "local:helloits" and introtts == "it's":
						introtts = ""

					text = introtts + " " + await self.fix_name(name)
					print(text + " joined the channel")

					await asyncio.sleep(3)
					if not introclip is None:
						await self.play_clip(introclip, after.channel)
					await self.play_clip("tts:" + text, after.channel)
		except UserError as e:
			print(f"Bad voice channel connection to ({channel_id}) from on_voice_state_update: {e.message}")


def setup(bot):
	bot.add_cog(Audio(bot))
