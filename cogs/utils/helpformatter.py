import discord, itertools, inspect
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

		# we need a padding of ~80 or so

		description = self.command.description if not self.is_cog() else inspect.getdoc(self.command)

		if description:
			# <description> portion
			embed = discord.Embed(description=description)
		else:
			embed = discord.Embed()

		if isinstance(self.command, Command):
			if self.command.help:
				embed = discord.Embed(description=self.command.help)

			embed.set_author(name=self.get_command_signature())

			return embed

		def category(tup):
			cog = tup[1].cog_name
			# we insert the zero width space there to give it approximate
			# last place sorting position.
			return cog + ':' if cog is not None else '\u200bNo Category:'

		if self.is_bot():
			data = sorted(self.filter_command_list(), key=category)
			for category, commands in itertools.groupby(data, key=category):
				# there simply is no prettier way of doing this.
				commands = list(commands)
				if len(commands) > 0:
					embed.add_field(name=category, value=self.list_commands(commands))
		else:
			# This is a cog
			embed.add_field(name="Commands", value=self.list_commands(self.filter_command_list()))

		# add the ending note
		print(self.get_ending_note())
		return embed



#need to figure out where this is converted to a message, and modify that there, so we can make it an embed. also, we can make the command character {cmdchar} configurable here, so yay

# bot.py: https://github.com/Rapptz/discord.py/blob/e2de93e2a65960c9c83e8a2fe53d18c4f9600196/discord/ext/commands/bot.py
# helpformatter: https://github.com/Rapptz/discord.py/blob/89eb3392afbb25df8a59e6bdd61531e90e48bbb8/discord/ext/commands/formatter.py

# Use this as new command
# gotta call remove_command("help") on startup so we can haz this command