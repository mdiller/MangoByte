import discord
import asyncio
import shutil
from discord.ext import commands
from __main__ import settings, botdata, httpgetter, loggingdb_session
from cogs.utils.helpers import *
from cogs.utils.botdata import GuildInfo
from cogs.utils.clip import GttsLang
from cogs.utils import checks
from cogs.utils import loggingdb
from cogs.utils import botdatatypes
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
			if not ctx.message.guild:
				raise UserError("You have to say that in a server")
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
			cmdpfx = botdata.command_prefix(ctx)
			raise UserError(f"There was a timeout when attempting to do the `{cmdpfx}summon`")
		await ctx.message.add_reaction("✅")


	@commands.command()
	async def unsummon(self, ctx):
		"""Removes the bot from the voice channel it is currently in"""
		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		if not ctx.message.guild:
			raise UserError("You have to say that in a server")
		await audio.disconnect(ctx.message.guild)
		botdata.guildinfo(ctx.message.guild.id).voicechannel = None
		await ctx.message.add_reaction("✅")


	@commands.command()
	async def resummon(self, ctx):
		"""Removes and then re-summons the bot to the voice channel

		This command is useful if you are having issues with mangobyte not being responsive"""
		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		if not ctx.message.guild:
			raise UserError("You have to be in a server to use this command")

		guildinfo = botdata.guildinfo(ctx.message.guild.id)

		save_channel = False
		channel = None
		if ctx.message.guild.me.voice:
			channel = ctx.message.guild.me.voice.channel
		elif ctx.message.author.voice:
			channel = ctx.message.author.voice.channel
		elif guildinfo.voicechannel is not None:
			channel = self.bot.get_channel(guildinfo.voicechannel)
		else:
			raise UserError("I'm not sure where you want me to resummon to. I'm not in any channel currently.")

		await audio.disconnect(ctx.message.guild)

		await asyncio.sleep(1)

		try:
			await audio.connect_voice(channel)
			guildinfo.voicechannel = channel.id
		except asyncio.TimeoutError:
			cmdpfx = botdata.command_prefix(ctx)
			raise UserError(f"There was a timeout when attempting to do the `{cmdpfx}summon`")

		await ctx.message.add_reaction("✅")

	@commands.command()
	async def config(self, ctx, name, *, value = None):
		"""Configures the bot's settings for this server

		Below are the different settings that you can tweak to customize mangobyte for this server. You can get more information about a setting by typing `{cmdpfx}config <settingname>`, and you can configure a setting by typing `{cmdpfx}config <settingname> <value>`

		{config_help}
		"""
		var = next((v for v in GuildInfo.variables if v["key"] == name), None)
		if not var:
			vars_list = "\n".join(map(lambda v: f"`{v['key']}`", GuildInfo.variables))
			await ctx.send(f"There is no config setting called '{name}'. Try one of these:\n{vars_list}")
			return

		
		if not value: # We are just getting a value
			value = botdata.guildinfo(ctx.guild)[var["key"]]
			await ctx.send(embed=await botdatatypes.localize_embed(ctx, var, value, f"{self.cmdpfx(ctx)}config"))
		else: # We are setting a value
			value = await botdatatypes.parse(ctx, var, value)
			botdata.guildinfo(ctx.guild)[var["key"]] = value
			await ctx.message.add_reaction("✅")


def setup(bot):
	bot.add_cog(Admin(bot))