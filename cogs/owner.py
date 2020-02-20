import discord
import youtube_dl
import asyncio
import shutil
from sqlalchemy import desc
from discord.ext import commands
from __main__ import settings, botdata, httpgetter, loggingdb
from cogs.utils.helpers import *
from cogs.utils.botdata import GuildInfo
from cogs.utils.clip import GttsLang
from cogs.utils import checks
from cogs.utils import loggingdb as loggingdb_spec
from cogs.utils import botdatatypes
from .mangocog import *
from concurrent.futures import ThreadPoolExecutor

def youtube_download_func(youtube_id, video_file):
	ytdl_options = {
		'format': 'bestaudio/best',
		'extractaudio' : True,
		'audioformat' : "mp3",
		'outtmpl': video_file,
		'source_address': '0.0.0.0',
		'noplaylist' : True,
		'nooverwrites': True,
	}
	with youtube_dl.YoutubeDL(ytdl_options) as ytdl:
		ytdl.download([youtube_id])

class Owner(MangoCog):
	"""Owner commands
	
	Only used by the bot owner, for managing the bot"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	def cog_check(self, ctx):
		"""Checks to make sure the user is the bot owner"""
		return checks.is_owner_check(ctx.message.author)

	async def youtube_download(self, youtube_id, video_file):
		return await self.bot.loop.run_in_executor(ThreadPoolExecutor(max_workers=1), youtube_download_func, youtube_id, video_file)

	@commands.command()
	async def updateemoji(self, ctx, name=None):
		"""Updates the emoji information for the bot

		passing in a name will target that emoji specifically"""
		emoji_json = read_json(settings.resource("json/emoji.json"))
		with ctx.channel.typing():
			for emoji in ctx.guild.emojis:
				if name is None or name == emoji.name:
					imgpath = settings.resource(f"images/emojis/{emoji.name}.png")
					with open(imgpath, 'wb+') as f:
						f.write((await httpgetter.get(str(emoji.url), return_type="bytes")).read())
					emoji_json[emoji.name] = emoji.id
		write_json(settings.resource("json/emoji.json"), emoji_json)
		await ctx.send("done!")


	@commands.command()
	async def addclip(self, ctx, url, clipname, start, end, start_fade=0.25, end_fade=0.25):
		"""Adds a clip from youtube"""
		outfile = settings.resource(f"clips/{clipname}.mp3")
		start = get_time(start)
		end = get_time(end)
		duration = end - start

		matches = [
			re.match(r"https?://(?:www\.)?youtube\.com/watch\?v=([^/]*)", url),
			re.match(r"https?://(?:www\.)?youtu\.be/([^/]*)", url),
			re.match(r"([^/]*)", url)
		]
		youtube_id = None
		for match in matches:
			if match:
				youtube_id = match.group(1)
				break
		if youtube_id is None:
			raise UserError("This doesnt look like a youtube url or an id")

		video_file = settings.resource(f"cache/youtube/{youtube_id}.mp3")

		if not os.path.exists(video_file):
			await self.youtube_download(youtube_id, video_file)

		fadefilter = f"afade=t=in:ss=0:d={start_fade},afade=t=out:st={duration - end_fade}:d={end_fade}"

		# Converting / Cropping
		run_command(["ffmpeg", "-ss", str(start), "-t", str(duration), "-y", "-i", video_file, "-af", fadefilter, outfile ])

		audio = self.bot.get_cog("Audio")
		audio.local_clipinfo[clipname] = OrderedDict([
			('path', f"{clipname}.mp3"),
			('source', f"https://www.youtube.com/watch?v={youtube_id}"),
			('start', start),
			('end', end)
		])
		audio.save_local_clipinfo()

		# Playing
		await self.play_clip(f"local:{clipname}", ctx)

	@commands.command(aliases=["editclip"])
	async def editclipinfo(self, ctx, clipname, attribute, *, value):
		"""Allows editing of a clip's info

		warning: volume actually edits the clip, and is a multiplier (0.5 cuts in half, 2 doubles)

		Example:
		`{cmdpfx}editclipinfo wow text Waow!`"""
		audio = self.bot.get_cog("Audio")
		if clipname not in audio.local_clipinfo:
			raise UserError("That clip doesn't exist")

		attribs = [
			"text",
			"author",
			"source",
			"start",
			"end"
		]

		if value is None or value == "":
			raise UserError("Gotta gimme a value")

		if attribute == "volume":
			filename = settings.resource("clips/" + audio.local_clipinfo[clipname]["path"])
			temp_file = settings.resource(f"temp/temp_{clipname}" + os.path.splitext(filename)[1])
			run_command(["ffmpeg", "-i", filename, "-af", f"volume={value}", temp_file])
			shutil.copyfile(temp_file, filename)
			os.remove(temp_file)
			await self.play_clip(f"local:{clipname}", ctx)
			await ctx.message.add_reaction("✅")
			return

		if attribute not in attribs:
			attribs_string = "\n".join(attribs)
			raise UserError(f"Invalid attribute name, try one of these:```\n{attribs_string}\n```")

		audio.local_clipinfo[clipname][attribute] = value
		audio.save_local_clipinfo()
		await ctx.message.add_reaction("✅")

	@commands.command(aliases=["botdata"])
	async def getbotdata(self, ctx, selector, identifier : int):
		"""Gets info about a user or a server"""
		if selector in ["user", "player", "member"]:
			data = botdata.userinfo(identifier)
			user = self.bot.get_user(identifier)
			if user is None:
				raise UserError("Couldn't find that user")

			embed = discord.Embed(description=(user.mention + "\n```json\n" + json.dumps(data.json_data, indent='\t') + "\n```"))
			embed.set_thumbnail(url=user.avatar_url)
			if data.steam:
				embed.add_field(name="Profiles", value=(
					f"[Steam](http://steamcommunity.com/id/{data.steam})\n"
					f"[OpenDota](https://www.opendota.com/players/{data.steam})\n"))
			await ctx.send(embed=embed)
		elif selector in ["server", "guild"]:
			data = botdata.guildinfo(identifier)
			guild = self.bot.get_guild(identifier)
			if guild is None:
				raise UserError("Couldn't find that guild")
			invite = None
			for channel in guild.text_channels:
				if channel.permissions_for(guild.me).create_instant_invite:
					invite = await channel.create_invite()
					break

			embed = discord.Embed(description=("```json\n" + json.dumps(data.json_data, indent='\t') + "\n```"))
			embed.set_author(name=guild.name)
			if guild.icon_url != "":
				embed.set_thumbnail(url=guild.icon_url)
			embed.add_field(name="Region", value=guild.region)
			embed.add_field(name="Member Count", value=guild.member_count)
			if invite:
				embed.add_field(name="Invite", value=invite.url)
			await ctx.send(embed=embed)

	@commands.command()
	async def clearcache(self, ctx, uri):
		"""Clears the cache at the given uri

		or clears everything from cache if given the 'all' keyword"""
		try:
			await httpgetter.cache.remove(uri)
		except KeyError:
			raise UserError("Couldn't find a cached version of that")

		await ctx.message.add_reaction("✅")

	@commands.command()
	async def getcache(self, ctx, uri):
		"""Gets the file in the cache that is pointed to by the uri"""
		filename = httpgetter.cache.get_filename(uri)

		if filename is None:
			raise UserError("Couldn't find a file at that uri")

		await ctx.send(file=discord.File(filename))

	@commands.command()
	async def errors(self, ctx, count : int=5, page : int=0, excludestring=None):
		"""Gets a list of the most recent errors from loggingdb"""

		for error in loggingdb.session.query(loggingdb_spec.Error).order_by(desc(loggingdb_spec.Error.timestamp)).offset(page * count):
			if count <= 0:
				return
			error_chunks = error.error_text_chunks()
			try:
				if excludestring and re.search(excludestring, "\n".join(error_chunks)):
					continue # skip this because our excludestring matches
			except Exception:
				raise UserError("Regex parsing error")
			await ctx.send(embed=error.to_embed(self))
			for chunk in error_chunks[:-1]:
				await ctx.send(chunk)
				await asyncio.sleep(0.5)

			await ctx.send(error_chunks[-1] + "\n_ _")
			await asyncio.sleep(0.5)
			count -= 1

	@commands.command()
	async def remoteresummon(self, ctx, guild_id : int):
		"""Removes and then re-summons the bot to the voice channel of the guild

		This command is useful if you are having issues with mangobyte not being responsive"""
		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")

		guild = self.bot.get_guild(guild_id)

		if guild is None:
			raise UserError(f"guild '{guild_id}' not found")

		guildinfo = botdata.guildinfo(guild_id)

		channel = None
		if guild.me.voice:
			channel = guild.me.voice.channel
		elif guildinfo.voicechannel is not None:
			channel = self.bot.get_channel(guildinfo.voicechannel)
		else:
			raise UserError("I'm not sure where you want me to resummon to. I'm not in any channel currently.")

		await audio.disconnect(guild)

		await asyncio.sleep(1)

		try:
			await audio.connect_voice(channel)
			guildinfo.voicechannel = channel.id
		except asyncio.TimeoutError:
			cmdpfx = botdata.command_prefix(ctx)
			raise UserError(f"There was a timeout when attempting to do the `{cmdpfx}summon`")

		await ctx.message.add_reaction("✅")


	@commands.command(aliases=["logs", "logger"])
	async def loggingdb(self, ctx, table, identifier):
		"""Gets a list of the most recent errors from loggingdb"""
		if table in [ "error", "errors", "bugs", "bug" ]:
			table = loggingdb_spec.Error
			filterer = lambda q: q.filter_by(message_id=identifier)
		elif table in [ "message", "messages", "msg", "messages" ]:
			table = loggingdb_spec.Message
			filterer = lambda q: q.filter_by(id=identifier)
		elif table in [ "command", "commands", "cmd", "cmds" ]:
			table = loggingdb_spec.Command
			filterer = lambda q: q.filter_by(message_id=identifier)
		else:
			raise UserError("Dont know what table you're talking about")
		found = False
		for obj in filterer(loggingdb.session.query(table)):
			found = True
			await ctx.send(embed=obj.to_embed(self))
			if table == loggingdb_spec.Error:
				chunks = obj.error_text_chunks()
				for chunk in chunks:
					await ctx.send(chunk)
		if not found:
			raise UserError("Couldn't find anything for that")

def setup(bot):
	bot.add_cog(Owner(bot))