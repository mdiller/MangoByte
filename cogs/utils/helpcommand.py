from mangobyte import botdata, settings
import discord, itertools, inspect, re
from discord.ext.commands import *
from .botdata import GuildInfo, UserInfo
from .helpers import read_json, MENTION_PATTERN
from cogs.mangocog import simple_get_emoji


def get_config_help(variables, command):
	keys = []
	examples = []
	for var in variables:
		keys.append(f"`{var['key']}`")
		examples.append(f"`{'{cmdpfx}'}{command} {var['key']} {var['example']}`")
	keys = "\n".join(keys)
	examples = "\n".join(examples)
	return (
		f"**Settings:**\n"
		f"{keys}\n\n"
		f"**Examples**\n"
		f"{examples}")


text_help_server = "Feel free to visit the [Mangobyte Help Server/Guild](https://discord.gg/d6WWHxx) if you have any questions!"
text_category_help = "To get more information about a specific category, try `{cmdpfx}help <category>`"
text_command_help = "To get more information about a specific command, try `{cmdpfx}help <command>`"

class MangoHelpCommand(DefaultHelpCommand):
	def __init__(self, **options):
		options["verify_checks"] = False
		super().__init__(**options)

	@property
	def bot(self):
		return self.context.bot

	async def send_bot_help(self, mapping):
		no_category = '\u200b{0.no_category}:'.format(self)
		def get_category(command, *, no_category=no_category):
			cog = command.cog
			return cog.qualified_name + ':' if cog is not None else no_category

		if self.show_all:
			# ?help all
			embed = self.embed_description(f"{self.bot.description}\n\n{text_help_server}\n\n{text_category_help}\n{text_command_help}", self.bot)
			embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url, url="https://github.com/mdiller/MangoByte")

			filtered = await self.filter_commands(self.bot.commands, sort=True, key=get_category)
			to_iterate = itertools.groupby(filtered, key=get_category)

			for category, commands in to_iterate:
				if category == "Owner:":
					continue
				commands = list(commands)
				if len(commands) > 0:
					embed.add_field(name=category, value=self.list_commands(commands, only_name=True), inline=False)
		else:
			# ?help
			embed = self.embed_description(f"{self.bot.description}\n\n{text_help_server}\n\n{text_category_help}\nTo show all commands, try `{{cmdpfx}}help all`", self.bot)
			embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url, url="https://github.com/mdiller/MangoByte")
			for cog in self.bot.cogs:
				if cog == "Owner":
					continue
				embed.add_field(name=f"**{cog}**", value=self.cog_short_doc(self.bot.cogs[cog]), inline=False)
		await self.send_embed(embed)

	async def send_command_help(self, command):
		# ?help <command>
		embed = self.embed_description(command.help, command)
		embed.set_author(name=self.get_command_signature(command))
		if command.aliases:
			embed.add_field(name="Aliases", value=", ".join(command.aliases))
		await self.send_embed(embed)

	async def send_cog_help(self, cog):
		# ? help <cog>
		description = inspect.getdoc(cog)
		description += f"\n\n{text_command_help}"
		description += "\n\n**Commands:**\n" + self.list_commands(await self.filter_commands(cog.get_commands()))
		embed = self.embed_description(description, cog)
		embed.set_author(name=cog.__class__.__name__)
		# embed.add_field(name="Commands", value=self.list_commands(await self.filter_commands(cog.get_commands())))
		await self.send_embed(embed)

	async def send_embed(self, embed):
		dest = self.get_destination()
		await dest.send(embed=embed)

	# Overridden to ignore case for input, and to add the 'all' option
	async def command_callback(self, ctx, *, command=None):
		if command:
			command = command.lower()
			trimming_pattern = f"(^<|>$|^{re.escape(botdata.command_prefix(ctx))})"
			while re.match(trimming_pattern, command):
				command = re.sub(trimming_pattern, "", command)
			if command == "all":
				command = None
				self.show_all = True
			else:
				name = command
				if name in map(lambda c: c.lower(), ctx.bot.cogs):
					for cog in ctx.bot.cogs:
						if cog.lower() == name:
							command = cog
							break
		else:
			self.show_all = False

		await super().command_callback(ctx, command=command)

	def list_commands(self, commands, only_name=False):
		results = []
		commands = sorted(commands, key=lambda c: c.name) 
		for command in commands:
			if command.name in command.aliases:
				# skip aliases
				continue
			if only_name:
				results.append("`{{cmdpfx}}{0:{1}<30}`".format(command.name, u"\u00A0"))
			else:
				entry = '`{{cmdpfx}}{0:{2}<{width}} | {1}`'.format(command.name, command.short_doc, u"\u00A0", width=self.get_max_size(commands))
				results.append(self.shorten_text(entry))
		if results:
			return self.fill_template("\n".join(results))
		else:
			return "`<empty>`"
	
	def get_command_signature(self, command):
		return '%s%s %s' % (botdata.command_prefix(self.context), command.qualified_name, command.signature)

	def fill_template(self, text):
		text = re.sub("\{config_help\}", get_config_help(GuildInfo.variables, "config"), text)
		text = re.sub("\{userconfig_help\}", get_config_help(UserInfo.variables, "userconfig"), text)
		text = re.sub("\{cmdpfx\}", botdata.command_prefix(self.context), text)
		text = re.sub("\n`", u"\n\u200b`", text)
		return text

	def cog_short_doc(self, cog):
		return self.fill_template(inspect.getdoc(cog).split('\n')[0])

	def embed_description(self, description, helptarget):
		if not description:
			return discord.Embed()
		description = self.fill_template(description)
		guildinfo = botdata.guildinfo(self.context)
		if helptarget and guildinfo and guildinfo.is_disabled(helptarget):
			emoji = simple_get_emoji("command_disabled", self.context.bot)
			thing = "command" if isinstance(helptarget, Command) else "category"
			description = f"{emoji} *This {thing} has been disabled on this server*\n{description}"
		return discord.Embed(description=description, color=discord.Color.blue())
