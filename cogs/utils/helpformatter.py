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


	def format_as_embed(self, context, command_or_bot):
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
			embed = self.embed_description(self.command.description)
			data = sorted(self.filter_command_list(), key=category)
			for category, commands in itertools.groupby(data, key=category):
				# there simply is no prettier way of doing this.
				commands = list(commands)
				if len(commands) > 0:
					embed.add_field(name=category, value=self.list_commands(commands))
		else:
			embed = self.embed_description(inspect.getdoc(self.command))
			embed.set_author(name=self.command.__class__.__name__)
			# This is a cog
			embed.add_field(name="Commands", value=self.list_commands(self.filter_command_list()))

		# add the ending note
		return embed

	def embed_description(self, description):
		if not description:
			return discord.Embed()
		description = re.sub("\{cmdpfx\}", self.context.bot.command_prefix, description)
		return discord.Embed(description=description)
