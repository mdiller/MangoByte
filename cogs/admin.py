import discord
from discord.ext import commands
from __main__ import settings, botdata
from cogs.utils.helpers import *
from cogs.utils import checks
from .mangocog import *


class Admin(MangoCog):
	"""Administrative commands
	
	Primarily used to stop people from ruining stuff, and to configure mangobyte to do different things."""
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
		if isinstance(ctx.channel, discord.abc.PrivateChannel):
			return False # All admin commands should be guild specific and not work on PM channels
		if checks.is_owner_check(ctx.message.author):
			return True
		perms = ctx.channel.permissions_for(ctx.message.author)
		return perms.administrator

	@commands.command()
	async def botban(self, ctx, user: discord.Member):
		"""Bans the user from using commands"""
		if checks.is_owner_check(user):
			await ctx.send("Ya can't ban mah owner, man. 😠")
			return
		if checks.is_admin_check(ctx.message.channel, user):
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
		await audio.connect_voice(channel)
		botdata.guildinfo(channel.guild.id).voicechannel = channel.id

	@commands.command()
	async def unsummon(self, ctx):
		"""Removes the bot from the voice channel it is currently in"""
		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		await audio.disconnect(ctx.message.guild)
		botdata.guildinfo(ctx.message.guild.id).voicechannel = None

	@commands.command()
	async def ttschannel(self, ctx, channel : discord.TextChannel):
		"""Sets a channel as the "TTS Channel"

		If someone types in this channel, mangobyte will automatically interpret it as a `{cmdpfx}smarttts` command

		**Example:** (If your channel name is tts)
		`{cmdpfx}ttschannel #tts`
		"""
		botdata.guildinfo(channel.guild.id).ttschannel = channel.id
		await ctx.send(f"{channel.mention} has been set as the tts channel!")

	@commands.command()
	async def unttschannel(self, ctx):
		"""Un-sets the "TTS Channel"

		See `{cmdpfx}ttschannel` for more info on what this is about
		"""
		if not botdata.guildinfo(ctx.message.guild.id).ttschannel:
			await ctx.send("TTS Channel has not been set. Try `?ttschannel <name of channel>`")
			return
		botdata.guildinfo(ctx.message.guild.id).ttschannel = None
		await ctx.send("TTS Channel removed")


def setup(bot):
	bot.add_cog(Admin(bot))
