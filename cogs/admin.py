import discord
from discord.ext import commands
from __main__ import settings, botdata, httpgetter
from cogs.utils.helpers import *
from cogs.utils.botdata import GuildInfo
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


def setup(bot):
	bot.add_cog(Admin(bot))
