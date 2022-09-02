import asyncio

import disnake
from disnake.ext import commands
from utils.command import botdatatypes, checks
from utils.tools.botdata import GuildInfo
from utils.tools.globals import botdata, logger
from utils.tools.helpers import *

from .mangocog import *

perms_cmd_deprecation_message = "**Note:** This command will soon be *deprecated*. Check out `/docs Command and User Permissions` for more info."

class Admin(MangoCog):
	"""Commands to help manage mangobyte on your server/guild
	
	Primarily used to configure mangobyte for this particular server/guild, and also for moving in and out of voice channels.

	Only admins or people with the correct role can use these commands. To set a role as the 'Bot Admin' role, try `/config botadmin`. Note that the `/summon` and `/unsummon` commands can be configured to be usable by everyone via `/config restrictsummoning disable`.
	"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
	
	def bot_check(self, ctx_inter: InterContext):
		"""Checks to make sure the user has permissions"""
		commandname = ""
		cog = None
		guildinfo = botdata.guildinfo(ctx_inter)
		if isinstance(ctx_inter, disnake.Interaction):
			if isinstance(ctx_inter, disnake.CommandInter):
				commandname = slash_command_name(ctx_inter)
			# check cogs
			cog = ctx_inter.application_command.cog
			if cog:
				if not cog.cog_check(ctx_inter):
					return False
		else:
			commandname = ctx_inter.command
			cog = ctx_inter.cog
		
		if guildinfo and ctx_inter.channel.type != disnake.ChannelType.private:
			if guildinfo.is_banned(ctx_inter.author):
				return False
			if guildinfo.is_disabled(commandname):
				return False
			if guildinfo.is_disabled(cog):
				return False
		return True

	def cog_check(self, ctx_inter: InterContext):
		"""Checks to make sure the user has admin privilages"""
		is_summoning_command = slash_command_name(ctx_inter) in ["summon", "unsummon"]
		if is_summoning_command and ctx_inter.guild and not botdata.guildinfo(ctx_inter.guild).restrictsummoning:
			return True
		return checks.is_admin_check(ctx_inter)

	@commands.slash_command()
	async def botunban(self, inter: disnake.CmdInter, user: disnake.Member):
		"""Unbans the user, allowing them to use commands. Note this will soon be deprecated.
		
		Parameters
		----------
		user: The user to unban
		"""
		await inter.response.defer()
		if inter.guild is None:
			await inter.send(f"You must be in a server/guild to use this command\n{perms_cmd_deprecation_message}")
			return
		if checks.is_owner_check(user) or user == self.bot.user:
			await inter.send(f"Ha ha. Very funny.\n{perms_cmd_deprecation_message}")
			return
		botdata.guildinfo(inter.guild).botunban(user)
		await inter.send(f"{user.mention} is free of their restraints and may once again use commands\n{perms_cmd_deprecation_message}")

	def get_command_or_cog(self, bot: commands.Bot, text):
		result = bot.cogs.get(text)
		if result is not None:
			return result
		result = bot.get_command(text)
		if result is not None:
			return result
		result = bot.get_slash_command(text)
		if result is not None:
			return result
		text = text.lower()
		for cog in bot.cogs:
			if text == cog.lower():
				return bot.cogs[cog]
		return None

	@commands.slash_command()
	async def enablecommand(self, inter: disnake.CmdInter, command: str):
		"""Re-enables the specified command or command category. Note this will soon be deprecated.
		
		Parameters
		----------
		command: The command or cog to re-enable
		"""
		await inter.response.defer()
		if inter.guild is None:
			await inter.send(f"You must be in a server/guild to use this command\n{perms_cmd_deprecation_message}")
			return
		guildinfo = botdata.guildinfo(inter.guild)
		if not guildinfo:
			raise UserError(f"This command must be called in a guild\n{perms_cmd_deprecation_message}")
		cmd = self.get_command_or_cog(inter.bot, command)
		if cmd is None:
			raise UserError(f"Couldn't find a command or command category by that name\n{perms_cmd_deprecation_message}")
		if not guildinfo.is_disabled(cmd.name):
			if guildinfo.is_disabled(cmd):
				raise UserError(f"This command is not disabled, but its category ({cmd.cog_name}) is\n{perms_cmd_deprecation_message}")
			else:
				raise UserError(f"This is not currently disabled\n{perms_cmd_deprecation_message}")
		guildinfo.enable_command(cmd.name)
		await inter.send(f"✅ Done!\n{perms_cmd_deprecation_message}")

	@commands.slash_command()
	async def summon(self, inter: disnake.CmdInter, channel : disnake.VoiceChannel = None):
		"""Summons the bot to the voice channel
		
		Parameters
		----------
		channel: The voice channel to summon to. Will summon to the one that you're in if you don't specify
		"""
		await inter.response.defer()
		if not channel:
			if not inter.guild:
				raise UserError("You have to say that in a server")
			if not inter.author.voice:
				raise UserError("You are not currently in a voice channel")
			channel = inter.author.voice.channel
			if channel.guild != inter.guild:
				raise UserError("You are not currently in a voice channel on this server/guild")

		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		try:
			if botdata.guildinfo(channel.guild.id).voicechannel == channel.id:
				await audio.disconnect(inter.guild)
				await asyncio.sleep(1)
			await audio.connect_voice(channel)
			botdata.guildinfo(channel.guild.id).voicechannel = channel.id
		except asyncio.TimeoutError:
			raise UserError("There was a timeout when attempting to do the `/summon`")
		await inter.send(f"✅ Summoned!")

	@commands.slash_command()
	async def unsummon(self, inter: disnake.CmdInter):
		"""Removes the bot from the voice channel"""
		await inter.response.defer()
		if not inter.guild:
			raise UserError("You must be in a server/guild to use this command")
		audio = self.bot.get_cog("Audio")
		if not audio:
			raise UserError("You must have the Audio cog enabled to do this")
		await audio.disconnect(inter.guild)
		botdata.guildinfo(inter.guild.id).voicechannel = None
		await inter.send(f"✅ Unsummoned!")

	@commands.slash_command()
	async def config(self, inter: disnake.CmdInter, setting: commands.option_enum(GuildInfo.keys_list()), value: str):
		"""Configures the bot's settings for this server/guild

		Parameters
		----------
		setting: The setting you'd like to show/change
		value: The value you'd like to set for this setting, or 'show' to see the current value and more info
		"""
		await inter.response.defer()
		if inter.guild is None:
			await inter.send("You must be in a server/guild to use this command")
			return
		if value == "show":
			value = None
		var = next((v for v in GuildInfo.variables if v["key"] == setting), None)
		
		currentvalue = botdata.guildinfo(inter.guild)[var["key"]]
		if not value: # We are just getting a value
			await inter.send(embed=await botdatatypes.localize_embed(inter, var, currentvalue, f"/config"))
		else: # We are setting a value
			value = await botdatatypes.parse(inter, var, value, currentvalue)
			botdata.guildinfo(inter.guild)[var["key"]] = value
			await inter.send(f"✅ {setting} has been set!")


def setup(bot):
	bot.add_cog(Admin(bot))
