import discord
import youtube_dl
import asyncio
import shutil
from discord.ext import commands
from __main__ import settings, botdata, httpgetter
from cogs.utils.helpers import *
from cogs.utils.botdata import GuildInfo
from cogs.utils.clip import GttsLang
from cogs.utils import checks
from .mangocog import *

class Admin(MangoCog):
	"""Administrative commands
	
	Primarily used to stop people from ruining stuff, and to configure mangobyte to do different things.

	Only admins or people with the correct role can use these commands. To set a role as the 'Bot Admin' role, try `{cmdpfx}config botadmin`"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	def __global_check(self, ctx):
		"""Checks to make sure the user has permissions"""
		if not isinstance(ctx.message.channel, discord.abc.PrivateChannel):
			if botdata.guildinfo(ctx.message.guild).is_banned(ctx.message.author):
				return False
		return True

	def __local_check(self, ctx):
		"""Checks to make sure the user has admin privilages"""
		return checks.is_admin_check(ctx.message.channel, ctx)

	@commands.command()
	async def botban(self, ctx, user: discord.Member):
		"""Bans the user from using commands"""
		if checks.is_owner_check(user):
			await ctx.send("Ya can't ban mah owner, man. 😠")
			return
		if checks.is_admin_check(ctx.message.channel, ctx, user):
			await ctx.send("Ya can't ban other admins")
			return
		if user.id == self.bot.user.id:
			await ctx.send("Lol you can't ban me, silly")
			return
		botdata.guildinfo(ctx.message.guild).botban(user)
		await ctx.send("{} has henceforth been banned from using commands 😤".format(user.mention))

	@commands.command()
	async def botunban(self, ctx, user: discord.Member):
		"""Unbans the user, allowing them to use commands"""
		if checks.is_owner_check(user) or user == self.bot.user:
			await ctx.send("Ha ha. Very funny.")
			return
		botdata.guildinfo(ctx.message.guild).botunban(user)
		await ctx.send("{} is free of their restraints and may once again use commands".format(user.mention))

	@commands.command()
	async def summon(self, ctx, channel : discord.VoiceChannel = None):
		"""Summons the bot to the voice channel you are currently in

		You can specify the specific voice channel that you would like to connect to. If no channel is specified, it will connect to whatever channel you are currently in.
		**Example:**
		`{cmdpfx}summon General`"""
		if not channel:
			if not ctx.message.author.voice:
				raise UserError("You are not currently in a voice channel")
			channel = ctx.message.author.voice.channel
			if channel.guild != ctx.message.guild:
				raise UserError("You are not currently in a voice channel on this server/guild")

		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		try:
			await audio.connect_voice(channel)
			botdata.guildinfo(channel.guild.id).voicechannel = channel.id
		except asyncio.TimeoutError:
			raise UserError("There was a timeout when attempting to do the `?summon`")


	@commands.command()
	async def unsummon(self, ctx):
		"""Removes the bot from the voice channel it is currently in"""
		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		await audio.disconnect(ctx.message.guild)
		botdata.guildinfo(ctx.message.guild.id).voicechannel = None
	

	config_aliases = {
		True: [ "enable", "enabled", "true", "yes" ],
		False: [ "disable", "disabled", "false", "no" ],
		"default": [ "reset", "clear", "none", "null" ]
	}

	async def config_get(self, var, value):
		embed = discord.Embed(description=var["description"])
		embed.set_author(name=var["key"])
		if var["type"] == bool:
			embed.add_field(name="Value", value="enabled" if value else "disabled")
		elif var["type"] == discord.TextChannel:
			embed.add_field(name="Value", value=f"<#{value}>" if value else "None")
		elif var["type"] == discord.Role:
			embed.add_field(name="Value", value=f"<@&{value}>" if value else "None")
		elif var["type"] == "GttsLang":
			embed.add_field(name="Value", value=GttsLang(value).pretty)
		else:
			raise ValueError("I don't know how to parse this type")
		embed.add_field(name="Example", value=f"`?config {var['key']} {var['example']}`")
		return embed

	async def config_set_parse(self, ctx, var, value):
		if value in [ "default", "reset", "clear", "none", "null" ]:
			return var["default"]

		if var["type"] == bool:
			if value.lower() in [ "enable", "enabled", "true", "yes" ]:
				return True
			elif value.lower() in [ "disable", "disabled", "false", "no" ]:
				return False
			else:
				raise UserError("Invalid input. Give me something like `enable` or `disable`")
		elif var["type"] == discord.TextChannel:
			try:
				channel = await commands.TextChannelConverter().convert(ctx, value)
				return channel.id
			except commands.BadArgument:
				raise UserError("Invalid input. Give me a channel reference like `#general`")
		elif var["type"] == discord.Role:
			try:
				channel = await commands.RoleConverter().convert(ctx, value)
				return channel.id
			except commands.BadArgument:
				raise UserError("Invalid input. Give me a role reference like `@BotAdmin`")
		elif var["type"] == "GttsLang":
			lang = GttsLang.get(value)
			if lang is None:
				raise UserError("Invalid input. See https://github.com/mdiller/MangoByte/blob/master/resource/json/gtts_languages.json for valid langs")
			else:
				return lang.lang
		else:
			raise ValueError("I don't know how to parse this type")
		embed.add_field(name="Example", value=f"`?config {var['key']} {var['example']}`")
		return embed

	@commands.command()
	async def config(self, ctx, name, value = None):
		"""Configures the bot's settings for this server

		Below are the different settings that you can tweak to customize mangobyte for this server. You can get more information about a setting by typing `?config <settingname>`, and you can configure a setting by typing `?config <settingname> <value>`

		{config_help}
		"""
		var = next((v for v in GuildInfo.variables if v["key"] == name), None)
		if not var:
			vars_list = "\n".join(map(lambda v: f"`{v['key']}`", GuildInfo.variables))
			await ctx.send(f"There is no config setting called '{name}'. Try one of these:\n{vars_list}")
			return

		
		if not value: # We are just getting a value
			value = botdata.guildinfo(ctx.guild)[var["key"]]
			await ctx.send(embed=await self.config_get(var, value))
		else: # We are setting a value
			value = await self.config_set_parse(ctx, var, value)
			botdata.guildinfo(ctx.guild)[var["key"]] = value
			await ctx.message.add_reaction("✅")

	@checks.is_owner()
	@commands.command(hidden=True)
	async def updateemoji(self, ctx):
		"""Updates the emoji information for the bot"""
		emoji_json = read_json(settings.resource("json/emoji.json"))
		with ctx.channel.typing():
			for emoji in ctx.guild.emojis:
				imgpath = settings.resource(f"images/emojis/{emoji.name}.png")
				with open(imgpath, 'wb+') as f:
					f.write((await httpgetter.get(emoji.url, return_type="bytes")).read())
				emoji_json[emoji.name] = f"<:{emoji.name}:{emoji.id}>"
		write_json(settings.resource("json/emoji.json"), emoji_json)
		await ctx.send("done!")


	@checks.is_owner()
	@commands.command(hidden=True)
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

		options = {
			'format': 'bestaudio/best',
			'extractaudio' : True,
			'audioformat' : "mp3",
			'outtmpl': video_file,
			'source_address': '0.0.0.0',
			'noplaylist' : True,
			'nooverwrites': True,
		}
		if not os.path.exists(video_file):
			with youtube_dl.YoutubeDL(options) as ydl:
				ydl.download([youtube_id])

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

	@checks.is_owner()
	@commands.command(hidden=True, aliases=["editclip"])
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

	@checks.is_owner()
	@commands.command(hidden=True, aliases=["botdata"])
	async def getbotdata(self, ctx, selector, identifier : int):
		"""Gets info about a user or a server, depending on the selector given"""
		if selector in ["user", "player", "member"]:
			data = botdata.userinfo(identifier)
			user = self.bot.get_user(identifier)
			if user is None:
				raise UserError("Couldn't find that user")

			embed = discord.Embed(description=(user.mention + "\n```json\n" + json.dumps(data.json_data, indent='\t') + "\n```"))
			embed.set_thumbnail(url=user.avatar_url)
			if data.steam32:
				embed.add_field(name="Profiles", value=(
					f"[Steam](http://steamcommunity.com/id/{data.steam32})\n"
					f"[OpenDota](https://www.opendota.com/players/{data.steam32})\n"))
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
			if invite:
				embed.add_field(name="Invite", value=invite.url)
			await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(Admin(bot))
