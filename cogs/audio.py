import asyncio
import math
import os
import queue
import re
import shutil
from typing import List
import urllib.request
from ctypes.util import find_library
from random import randint

import disnake
from disnake.ext import commands, tasks
from utils.command import botdatatypes
from utils.command.clip import *
from utils.command.paginator import Paginator
from utils.tools.globals import botdata, logger, settings
from utils.tools.helpers import *
from utils.other.errorhandling import report_error

from cogs.mangocog import *

CLIPS_ITEMS_PER_PAGE = 20
URL_CLIP_ERROR_MESSAGE = "Unfortunatley I'm removing the url clip feature for now. I've got plans to eventually implement some custom clips that will be even more flexible than this, but I'm not sure when that feature will arrive."

intro_outro_length = 4.5
voice_channel_culling_timeout_hours = 24 * 4 # 24 * 4 means after 4 days of inactivity, mango will disconnect from the voice channel

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
			logger.info("removed temp file " + mp3name)


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
	
	@property
	def voice_channel_id(self):
		if self.voice is None:
			return None
		else:
			return self.voice.channel.id

	async def update_guild(self):
		self.guild = await self.bot.fetch_guild(self.guild.id)

	# re-assigns a fresh server object (hotfix to solve library issue)
	async def manually_kill_voice_client(self):
		logger.warn(f"manual kill info: guild:{self.guild_id}")
		logger.warn(f"manual kill info: channel info: (type:{type(self.voice.channel)}) attributes: {dir(self.voice.channel)}")
		self.bot._connection._remove_voice_client(self.guild_id)

	# connects to a voice channel
	async def connect(self, channel):
		if not isinstance(channel, disnake.VoiceChannel):
			channel = self.bot.get_channel(channel)

		voice = self.voice

		if voice is None:
			logger.info(f"attempting connect to: {channel.id}")
			await channel.connect()
			logger.info(f"finished connect to: {channel.id}")
		elif voice.channel and voice.channel.id == channel.id:
			logger.info(f"doin' a disconnect and reconnect for: {channel.id}")
			try:
				await voice.disconnect(force=True)
			except AttributeError:
				await self.manually_kill_voice_client()
			await asyncio.sleep(2)
			await channel.connect()
			logger.info(f"finished reconnect for: {channel.id}")
			# logger.info(f"leaving this because we're supposedly already connected? ({channel.id})")
		else:
			logger.info(f"attempting move to: {channel.id}")
			await voice.move_to(channel)
			logger.info(f"finished move to: {channel.id}")

	def done_talking(self, error):
		if error:
			logger.error(f"Error on voice.play: {error}")
		if not self.clipqueue.empty():
			coro = self.play_next_clip()
			fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
			try:
				fut.result()
			except:
				logger.info(f"Error playing next clip")
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
			self.voice.play(disnake.FFmpegPCMAudio(clip.audiopath), after=self.done_talking)
		except disnake.errors.ClientException as e:
			if str(e) == "Not connected to voice.":
				raise UserError("Error playing clip. Try doing `/summon`.")
			else:
				raise

		self.voice.source = disnake.PCMVolumeTransformer(self.voice.source)
		self.voice.source.volume = clip.volume
		logger.info("playing: " + clip.audiopath)
		if self.last_clip != None and clip.audiopath != self.last_clip.audiopath:
			remove_if_temp(self.last_clip.audiopath)
		self.last_clip = clip

	# try queueing an mp3 to play
	async def queue_clip(self, clip, ctx_inter: InterContext):
		if(self.voice is None):
			logger.warning("tried to talk while not in voice channel")
			raise AudioPlayerNotFoundError("not in voice channel m8")

		self.clipqueue.put(clip)

		if self.voice and not self.voice.is_playing():
			await self.play_next_clip()



class Audio(MangoCog):
	"""For playing audio in a voice channel

	The mangobyte audio system uses things called 'clips'. For more info on these, check out `/docs Clips`"""

	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.start_time = datetime.datetime.now()
		self.last_played_audio = {} # dict of the last time audio was played from a given server, used for voice channel culling
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
				path = os.path.join(root, file)
				match = re.search(f".*(?:{audio_extensions})$", os.path.join(root, file))
				if match:
					name, _ = os.path.splitext(file)
					path = os.path.relpath(path, clipsdir)
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
	async def audioplayer(self, ctx_inter: InterContext, error_on_none=True):
		target = ctx_inter
		if isinstance(ctx_inter, disnake.ext.commands.Context):
			if ctx_inter.message.guild is None: # This is a private channel, so give it user
				target = ctx_inter.message.author
			else:
				target = ctx_inter.message.guild
		elif isinstance(ctx_inter, disnake.Interaction):
			if ctx_inter.guild is None: # This is a private channel, so give it user
				target = ctx_inter.author
			else:
				target = ctx_inter.guild

		if isinstance(target, disnake.User):
			author = target
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
		elif isinstance(target, disnake.Guild):
			guild = target
		elif isinstance(target, disnake.abc.GuildChannel):
			guild = target.guild
		else:
			raise ValueError(f"Incorrect type '{type(target)}' given to audioplayer function")

		for audioplayer in self.audioplayers:
			if audioplayer.guild == guild:
				return audioplayer

		if error_on_none:
			raise AudioPlayerNotFoundError(f"I'm not in a voice channel on this server/guild. Have an admin do `/summon` to put me in one.")
		else:
			return None

	# Connects an audioplayer for the correct guild to the indicated channel
	async def connect_voice(self, channel):
		if not isinstance(channel, disnake.abc.GuildChannel):
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
		if guild.me and guild.me.voice:
			voice = next((voice for voice in self.bot.voice_clients if voice.guild == guild), None)
			if voice:
				logger.info("calling disconnect!")
				await voice.disconnect(force=True)
			else:
				logger.info("can't find voice to disconnect!\nvoices available:")
				for v in self.bot.voice_clients:
					logger.info(v.vcid)
		audioplayer = await self.audioplayer(guild, False)
		if audioplayer is not None:
			self.audioplayers.remove(audioplayer)

	@tasks.loop(hours=12)
	async def voice_channel_culler(self):
		logger.info("task_triggered: voice_channel_culler()")
		now = datetime.datetime.now()
		culling_cutoff = voice_channel_culling_timeout_hours * 60 * 60
		if (now - self.start_time).total_seconds() < culling_cutoff:
			return # Nothing to do yet, bot hasnt been up long enough to cull voice channels
		
		for guildinfo in botdata.guildinfo_list():
			if guildinfo.voicechannel is not None:
				if (guildinfo.id not in self.last_played_audio) or ((now - self.last_played_audio[guildinfo.id]).total_seconds() > culling_cutoff):
					# cull this voice channel
					logger.info(f"culling voice from server {guildinfo.id}")
					await self.disconnect(self.bot.get_guild(guildinfo.id))
					guildinfo.voicechannel = None

	
	@commands.slash_command()
	async def play(self, inter: disnake.CmdInter):
		"""Root command for clip-controlling commands"""
		await self.safe_defer(inter)

	@play.sub_command(name="local")
	async def play_local(self, inter: disnake.CmdInter, clipname: str):
		"""Plays a local audio clip. For more information on clips, see `/docs Clips`
		
		Parameters
		----------
		clipname: The name of a local audio clip, or a clipid
		"""
		if ":" not in clipname:
			try:
				await self.play_clip(f"local:{clipname}", inter, print=True)
			except ClipNotFound:
				dotabase = self.bot.get_cog("Dotabase")
				if dotabase:
					chat_clip = dotabase.get_chatwheel_sound_clip(clipname)
					if chat_clip:
						await self.play_clip(chat_clip, inter)
						return
				await inter.send(f"'{clipname}' is not a valid clip. 🤦 Try `/clip list`.")
		else:
			await self.play_clip(clipname, inter, print=True)


	@commands.slash_command()
	async def clips(self, inter: disnake.CmdInter):
		"""Root command for listing different kinds of clips"""
		await self.safe_defer(inter)
	

	async def clips_pager(self, inter: disnake.CmdInter, title: str, clipids: List[str], cliptext: List[str] = None, page: int = 1, more_pages: bool = False):
		"""A helper method for dumping a bunch of clips in one place. helps with the clips command."""
		if not clipids:
			await inter.send("No clips found!")
			return
		total_pages = math.ceil(len(clipids) / CLIPS_ITEMS_PER_PAGE)
		if page > total_pages:
			page = total_pages		
		
		view = Paginator(inter, self.clips_pager_embed, (clipids, cliptext), title, total_pages, page, more_pages=more_pages)
		embed = await view.get_page_embed(page)

		if total_pages == 1:
			await inter.send(embed=embed)
		else:
			await inter.send(embed=embed, view=view)
	
	async def clips_pager_embed(self, page: int, data):
		"""A helper method for creating an embed for the clips pager"""
		embed = disnake.Embed()
		clipids, cliptext = data
		page_clipids = clipids[(page - 1) * CLIPS_ITEMS_PER_PAGE:page * CLIPS_ITEMS_PER_PAGE]

		if cliptext:
			page_cliptext = cliptext[(page - 1) * CLIPS_ITEMS_PER_PAGE:page * CLIPS_ITEMS_PER_PAGE]
			embed.add_field(name="Clip IDs", value="\n".join(page_clipids))
			embed.add_field(name="Clip Message", value="\n".join(page_cliptext))
		else:
			embed.description = "\n".join(page_clipids)
		return embed

	@clips.sub_command(name="local")
	async def clips_local(self, inter: disnake.CmdInter, tag: str, page: commands.Range[int, 1, 99] = 1):
		"""Lists the names of local audio clips. For more info on clips, see '/docs Clips'

		Parameters
		----------
		tag: A way to filter for specific clips. Type "tags" to see possible tags, or "all" to show all clips
		page: Which page of clips to view
		"""
		header = "Local Audio Clips"
		clips = []
		sort = True

		if tag == "all":
			for clipname in self.local_clipinfo:
				clips.append(clipname)
		elif tag in [ "recent", "latest", "new" ]:
			clips = {}
			for clipname in self.local_clipinfo:
				clips[clipname] = os.path.getctime(settings.resource(f"clips/{self.local_clipinfo[clipname]['path']}"))
			clips = list(map(lambda x: x[0], sorted(clips.items(), key=lambda x: x[1], reverse=True)))
			clips = clips[:10]
			sort = False
		elif tag == "tags":
			header = "Local Audio Clip Tags"
			for clipname in self.local_clipinfo:
				tags = self.local_clipinfo[clipname].get("tags")
				if tags:
					tags = tags.split("|")
					for t in tags:
						if t not in clips:
							clips.append(t)
		else:
			header += f" [{tag}]"
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

		if tag != "tags":
			clips = list(map(lambda c: f"local:{c}", clips))
		if len(clips) > 0 and sort:
			clips.sort()
			
		await self.clips_pager(inter, header, clips, page=page)

	@commands.slash_command()
	async def stop(self, inter: disnake.CmdInter):
		"""Stops the currently playing clip"""
		await self.safe_defer(inter)
		audioplayer = await self.audioplayer(inter)
		while not audioplayer.clipqueue.empty():
			try:
				audioplayer.clipqueue.get()
			except queue.Empty:
				continue
		if audioplayer.voice is not None:
			audioplayer.voice.stop()
		await inter.send("✅ stopped!")

	@commands.slash_command()
	async def replay(self, inter: disnake.CmdInter):
		"""Replays the last played clip"""
		await self.safe_defer(inter)
		last_clip = (await self.audioplayer(inter)).last_clip
		if last_clip == None:
			await inter.send("Nobody said anythin' yet")
			return

		# If its not a temp file
		await self.play_clip(last_clip, inter, print=True)

	@commands.slash_command()
	async def clipinfo(self, inter: disnake.CmdInter, clipid: str = None):
		"""Gets information and a file for the given clip

		Parameters
		----------
		clipid: A clipid (see '/docs Clips' for more info) or leave this blank, which will get the last played clip
		"""
		await self.safe_defer(inter)
		if clipid is None:
			if (await self.audioplayer(inter)).last_clip == None:
				await inter.send("Nobody said anythin' yet")
				return
			clipid = (await self.audioplayer(inter)).last_clip.clipid

		try:
			clip = await self.get_clip(f"local:{clipid}", inter)
		except ClipNotFound:
			clip = await self.get_clip(clipid, inter)

		if clip.type() == "url":
			await inter.send(URL_CLIP_ERROR_MESSAGE)
			return
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

		await inter.send(embed=clip_info_embed, file=disnake.File(clip.audiopath, filename=filename))

	@play.sub_command(name="tts")
	async def play_tts(self, inter: disnake.CmdInter, message: str):
		"""Converts the given message to speech and plays the tts clip

		Parameters
		----------
		message: A message to convert to speech
		"""
		clip = await self.do_tts(message, inter)
		await self.print_clip(inter, clip)

	async def do_tts(self, text, clip_ctx: ClipContext):
		gtts_fixes = read_json(settings.resource("json/gtts_fixes.json"))
		text = text.replace("\n", " ")
		for key in gtts_fixes:
			pattern = f"\\b({key})\\b" if not key.startswith("regex:") else re.sub("^regex:", "", key)
			text = re.sub(pattern, gtts_fixes[key], text, re.IGNORECASE)
		return await self.play_clip("tts:" + text, clip_ctx)

	@commands.slash_command()
	async def say(self, inter: disnake.CmdInter, message: str):
		"""Plays a sound clip based on the message given, drawing from multiple clip types

		Parameters
		----------
		message: A message to say
		"""
		await self.safe_defer(inter)
		clip = await self.do_smarttts(message, inter)
		await self.print_clip(inter, clip)

	async def do_smarttts(self, message, clip_ctx: ClipContext):
		if message == "" or not message:
			return None # dont say anything if theres nothin to be said
		if re.match(Clip.id_pattern, message):
			try: # try to play it if it looks like a full clipid
				return await self.play_clip(message, clip_ctx)
			except ClipNotFound:
				pass
		if re.match(r"^[\.0-9\-]+$", message): # if its just a number, do normal tts
			return await self.do_tts(message, clip_ctx)
		simple_message = re.sub(r'[^a-z0-9\s_]', r'', message.lower())
		dotabase = self.bot.get_cog("Dotabase")
		if dotabase:
			if simple_message in [ "haha", "lol", "laugh" ]:
				response = await dotabase.get_laugh_response()
				return await dotabase.play_response(response, clip_ctx)

			clip = dotabase.get_chatwheel_sound_clip(message)
			if clip:
				return await self.play_clip(clip, clip_ctx)
			query = await dotabase.smart_dota_query(message, exact=True)
			if query:
				return await dotabase.play_response_query(query, clip_ctx)

		if simple_message in self.local_clipinfo:
			return await self.play_clip(f"local:{simple_message}", clip_ctx)

		for clipname in self.local_clipinfo:
			clip = self.local_clipinfo[clipname]
			simple_text = re.sub(r'[^a-z0-9\s_]', r'', clip.get("text", "").lower())
			if simple_text == "":
				continue
			if simple_message == simple_text:
				return await self.play_clip(f"local:{clipname}", clip_ctx)

		return await self.do_tts(message, clip_ctx)

	@commands.Cog.listener()
	async def on_message(self, message: disnake.Message):
		if message.guild and message.author.id != self.bot.user.id:
			if message.content == "" or message.clean_content == "":
				return # weird empty messages should get ignored
			guildinfo = botdata.guildinfo(message.guild)
			userinfo = botdata.userinfo(message.author.id)
			if guildinfo.is_banned(message.author):
				return # banned users cant talk
			if userinfo.ignoremytts:
				return # ignore anyone who's configured the bot to ignore them
			if message.author.bot:
				if message.webhook_id:
					if not guildinfo.allowwebhooks:
						return # if this is a webhook then ignore it because we're not allowing it
				else:
					if message.author.id not in guildinfo.allowedbots:
						return # ignore bots unless theyre explicitly allowed
			ttschannel = guildinfo.ttschannel
			if ttschannel == message.channel.id:
				if message.content.startswith("//") or message.content.startswith("#"):
					return # commented out stuff should be ignored
				try:
					logger.event("tts", {
						"message_id": message.id,
						"author_id": message.author.id,
						"server_id": message.guild.id,
						"channel_id": message.channel.id,
						"timestamp": message.created_at.isoformat()
					})
					logger.event_info("TTS_MESSAGE_CONTENT", {
						"message_id": message.id,
						"author_id": message.author.id,
						"content": message.content,
						"clean_content": message.clean_content
					})
					if guildinfo.announcetts:
						name = message.author.name
						if guildinfo.usenickname and message.author.nick:
							name = message.author.nick
						name = await self.fix_name(name)
						await self.do_tts(f"{name} says", message.guild)
					if guildinfo.simpletts:
						await self.do_tts(message.clean_content, message.guild)
					else:
						await self.do_smarttts(message.clean_content, message.guild)
				except AudioPlayerNotFoundError as e:
					if not guildinfo.ttschannelwarn:
						return # just dont warn em if theyve said to not warn
					try:
						await message.channel.send(e.message)
					except disnake.errors.Forbidden as e:
						logger.warn("on_message usererror blocked because permissions")
						pass
				except UserError as e:
					try:
						await message.channel.send(e.message)
					except disnake.errors.Forbidden as e:
						logger.warn("on_message usererror blocked because permissions")
						pass
				except Exception as e:
					try:
						await message.channel.send("Uh-oh, sumthin dun gone wrong 😱")
					except disnake.errors.Forbidden as e:
						logger.warn("on_message usererror blocked because permissions")
						pass
					await report_error(message, TtsChannelError(e))

	# fixes discord user names which either are in all caps or have a number serving as a letter
	async def fix_name(self, name):
		# If all upper case or numbers n stuff, make all lower case
		name = str(name)
		if re.match(r"^[^a-z]*$", name):
			name = name.lower()

		# Simple replacing of all numbers that appear to be acting as letters
		letternumbers = { "0": "o", "1": "i", "3": "e", "4": "a", "7": "t" }
		for num in letternumbers:
			name = re.sub("{}([A-Za-z])".format(num), r"{}\1".format(letternumbers[num]), name)
		return name

	#function called when this event occurs
	@commands.Cog.listener()
	async def on_voice_state_update(self, member: disnake.Member, before: disnake.VoiceState, after: disnake.VoiceState):
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
					except Exception as e:
						logger.error(f"exception '{type(e)}' thrown when getting outro for {member.id}")
						outroclip = userinfo.outro

					outrotts = userinfo.outrotts
					name = member.global_name
					if guildinfo.usenickname and member.nick:
						name = member.nick


					text = (await self.fix_name(name)) + " " + outrotts
					logger.info(text)

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
					except Exception as e:
						logger.error(f"exception '{type(e)}' thrown when getting intro for {member.id}")
						introclip = userinfo.intro

					introtts = userinfo.introtts
					name = member.global_name
					if guildinfo.usenickname and member.nick:
						name = member.nick

					# Special case for default
					if userinfo.intro == "local:helloits" and introtts == "it's":
						introtts = ""

					text = introtts + " " + await self.fix_name(name)
					logger.info(text + " joined the channel")

					await asyncio.sleep(3)
					if not introclip is None:
						await self.play_clip(introclip, after.channel)
					await self.play_clip("tts:" + text, after.channel)
		except UserError as e:
			logger.error(f"Bad voice channel connection to ({channel_id}) from on_voice_state_update: {e.message}")

		
	@commands.slash_command()
	async def customclip(self, inter: disnake.CmdInter, target: commands.option_enum(["intro", "outro"]), clip: disnake.Attachment):
		"""Sets your intro or outro to a custom mp3 clip

		Parameters
		----------
		target: Whether you're setting your outro or your intro
		clip: A file to set as your clip. Must be an mp3 less than 4 seconds long."""
		await self.safe_defer(inter)
		print(f"setting {target} to {clip.filename}")

		clipnum = {
			"intro": "1",
			"outro": "2"
		}[target]

		clip_identifier = f"{inter.author.id}_{clipnum}"
		filename = CustomClip.get_clip_path(clip_identifier)

		temp_filename = filename.replace(".mp3", "_TEMP.mp3")
		await clip.save(temp_filename)
		
		# verify that it is less than 4 seconds
		clip_duration = round(float(run_command(["ffprobe", "-i", temp_filename, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"])), 2)
		if clip_duration > 4:
			os.remove(temp_filename)
			raise UserError("Custom clips for intros and outros must be less than 4 seconds long")
		
		# move the temp file to the right destination
		if os.path.exists(filename):
			os.remove(filename)
		shutil.copy(temp_filename, filename)
		os.remove(temp_filename)

		clipid = f"custom:{clip_identifier}"

		botdata.userinfo(inter.author)[target] = clipid
		await inter.send(f"✅ {target} has been set!")

def setup(bot):
	bot.add_cog(Audio(bot))
