from __main__ import botdata
import discord, itertools, inspect, re
from discord.ext.commands import *
from .botdata import GuildInfo, UserInfo

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

class MangoHelpFormatter(HelpFormatter):
	async def filter_command_list(self):
		"""Same as one from original formatter, but doesnt check to see if the checks fail"""

		def sane_no_suspension_point_predicate(tup):
			cmd = tup[1]
			if self.is_cog():
				# filter commands that don't exist to this cog.
				if cmd.instance is not self.command:
					return False

			if cmd.hidden and not self.show_hidden:
				return False
			return True

		iterator = self.command.all_commands.items() if not self.is_cog() else self.context.bot.all_commands.items()
		
		return filter(sane_no_suspension_point_predicate, iterator)

	def list_commands(self, commands):
		results = []
		for name, command in commands:
			if name in command.aliases:
				# skip aliases
				continue

			entry = '`{0:<{width}} | {1}`'.format(name, command.short_doc, width=self.max_name_size)
			shortened = self.shorten(entry)
			results.append(entry)
		if results:
			return "\n".join(results)
		else:
			return "`<empty>`"

	def fill_template(self, text):
		text = re.sub("\{config_help\}", get_config_help(GuildInfo.variables, "config"), text)
		text = re.sub("\{userconfig_help\}", get_config_help(UserInfo.variables, "userconfig"), text)
		text = re.sub("\{cmdpfx\}", botdata.command_prefix(self.context), text)
		return text

	def cog_short_doc(self, cog):
		return self.fill_template(inspect.getdoc(cog).split('\n')[0])

	async def format_as_embed(self, context, command_or_bot, show_all=False):
		self.context = context
		self.command = command_or_bot

		if isinstance(self.command, Command):
			embed = self.embed_description(self.command.help)
			embed.set_author(name=self.get_command_signature())
			if self.command.aliases:
				embed.add_field(name="Aliases", value=", ".join(self.command.aliases))
			return embed

		def category(tup):
			cog = tup[1].cog_name
			return cog + ':' if cog is not None else '\u200bNo Category:'

		if self.is_bot():
			if show_all:
				embed = self.embed_description(self.command.description + "\n\nTo get more information about a specific command, try `{cmdpfx}help <command>`")
				embed.set_author(name=self.command.user.name, icon_url=self.command.user.avatar_url, url="https://github.com/mdiller/MangoByte")
				data = sorted(await self.filter_command_list(), key=category)
				for category, commands in itertools.groupby(data, key=category):
					if category == "Owner:":
						continue
					commands = list(commands)
					if len(commands) > 0:
						embed.add_field(name=category, value=self.list_commands(commands))
			else:
				embed = self.embed_description(self.command.description + "\n\nTo get more information about a specific category, try `{cmdpfx}help <category>`")
				embed.set_author(name=self.command.user.name, icon_url=self.command.user.avatar_url, url="https://github.com/mdiller/MangoByte")
				for cog in self.command.cogs:
					if cog == "Owner":
						continue
					embed.add_field(name=f"**{cog}**", value=self.cog_short_doc(self.command.cogs[cog]))
		else:
			# This is a cog
			embed = self.embed_description(inspect.getdoc(self.command))
			embed.set_author(name=self.command.__class__.__name__)
			embed.add_field(name="Commands", value=self.list_commands(await self.filter_command_list()))

		return embed

	# Overridden to remove aliases
	def get_command_signature(self):
		"""Retrieves the signature portion of the help page."""
		result = []
		prefix = self.clean_prefix
		cmd = self.command
		parent = cmd.full_parent_name
		name = prefix + cmd.name if not parent else prefix + parent + ' ' + cmd.name
		result.append(name)

		params = cmd.clean_params
		if len(params) > 0:
			for name, param in params.items():
				if param.default is not param.empty:
					# We don't want None or '' to trigger the [name=value] case and instead it should
					# do [name] since [name=None] or [name=] are not exactly useful for the user.
					should_print = param.default if isinstance(param.default, str) else param.default is not None
					if should_print:
						result.append('[{}={}]'.format(name, param.default))
					else:
						result.append('[{}]'.format(name))
				elif param.kind == param.VAR_POSITIONAL:
					result.append('[{}...]'.format(name))
				else:
					result.append('<{}>'.format(name))

		return ' '.join(result)

	def embed_description(self, description):
		if not description:
			return discord.Embed()
		description = self.fill_template(description)
		return discord.Embed(description=description, color=discord.Color.blue())
