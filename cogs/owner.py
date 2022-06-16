import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor

import disnake
import youtube_dl
from disnake.ext import commands
from sqlalchemy import desc
from utils.command import checks
from utils.tools.globals import botdata, httpgetter, settings, logger
from utils.tools.helpers import *

from dotabase import Hero

from .mangocog import *


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

	def cog_check(self, ctx_inter: InterContext):
		"""Checks to make sure the user is the bot owner"""
		return checks.is_owner_check(ctx_inter.author)

	async def youtube_download(self, youtube_id, video_file):
		return await self.bot.loop.run_in_executor(ThreadPoolExecutor(max_workers=1), youtube_download_func, youtube_id, video_file)

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
		`?editclipinfo wow text Waow!`"""
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
			try:
				user = await self.bot.fetch_user(identifier)
			except:
				raise UserError("Couldn't find that user")

			embed = disnake.Embed(description=(user.mention + "\n```json\n" + json.dumps(data.json_data, indent='\t') + "\n```"))
			embed.set_thumbnail(url=user.avatar.url)
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

			embed = disnake.Embed(description=("```json\n" + json.dumps(data.json_data, indent='\t') + "\n```"))
			embed.set_author(name=guild.name)
			if guild.icon_url != "":
				embed.set_thumbnail(url=guild.icon_url)
			embed.add_field(name="Region", value=guild.region)
			embed.add_field(name="Member Count", value=guild.member_count)
			if invite:
				embed.add_field(name="Invite", value=invite.url)
			await ctx.send(embed=embed)

	@commands.command()
	async def remoteresummon(self, ctx, guild_id : int):
		"""Re-summons the bot for the given guild

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
			raise UserError(f"There was a timeout when attempting to do the `/summon`")

		await ctx.message.add_reaction("✅")

	@commands.command(aliases=["restart", "quit", "kill", "pokemango", "exit"])
	async def close(self, ctx):
		"""Kills the bot"""
		await self.bot.change_presence(status=disnake.Status.offline)
		await self.bot.close()

def setup(bot):
	bot.add_cog(Owner(bot))
