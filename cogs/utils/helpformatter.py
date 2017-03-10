import discord, itertools, inspect, re
from discord.ext.commands import *


class MangoHelpFormatter(HelpFormatter):
	def list_commands(self, commands):
		results = []
		for name, command in commands:
			if name in command.aliases:
				# skip aliases
				continue

			entry = '`{0:<{width}} {1}`'.format(name, command.short_doc, width=self.max_name_size)
			shortened = self.shorten(entry)
			results.append(entry)
		return "\n".join(results)


	def format_as_embed(self, context, command_or_bot, show_all=False):
		self.context = context
		self.command = command_or_bot

		if isinstance(self.command, Command):
			embed = self.embed_description(self.command.help)
			embed.set_author(name=self.get_command_signature())
			return embed

		def category(tup):
			cog = tup[1].cog_name
			return cog + ':' if cog is not None else '\u200bNo Category:'

		if self.is_bot():
			if show_all:
				embed = self.embed_description(self.command.description + "\n\nTo get more information about a specific command, try `{cmdpfx}help <command>`")
				embed.set_author(name=self.command.user.name, icon_url=self.command.user.avatar_url, url="https://github.com/mdiller/MangoByte")
				data = sorted(self.filter_command_list(), key=category)
				for category, commands in itertools.groupby(data, key=category):
					commands = list(commands)
					if len(commands) > 0:
						embed.add_field(name=category, value=self.list_commands(commands))
			else:
				embed = self.embed_description(self.command.description + "\n\nTo get more information about a specific category, try `{cmdpfx}help <category>`")
				embed.set_author(name=self.command.user.name, icon_url=self.command.user.avatar_url, url="https://github.com/mdiller/MangoByte")
				for cog in self.command.cogs:
					description = re.sub("\{cmdpfx\}", self.command.command_prefix, inspect.getdoc(self.command.cogs[cog]))
					embed.add_field(name=f"**{cog}**", value=description)
		else:
			# This is a cog
			embed = self.embed_description(inspect.getdoc(self.command))
			embed.set_author(name=self.command.__class__.__name__)
			embed.add_field(name="Commands", value=self.list_commands(self.filter_command_list()))

		return embed

	def embed_description(self, description):
		if not description:
			return discord.Embed()
		description = re.sub("\{cmdpfx\}", self.context.bot.command_prefix, description)
		return discord.Embed(description=description)
