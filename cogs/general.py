import discord
from discord.ext import commands
from discord.ext.commands.bot import _mention_pattern, _mentions_transforms
from __main__ import settings, botdata
from cogs.utils.helpers import *
from cogs.utils import checks
import asyncio
import aiohttp
import string
import random
import datetime
from .mangocog import *


class General(MangoCog):
	"""Basic and admin commands

	These commands are primarily used to stop people from ruining things"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)

	@commands.command(pass_context=True)
	async def ping(self, ctx, count : int=1):
		"""Pongs a number of times(within reason)

		Pongs... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await self.bot.say("thats not enough pings. stahp trying to break me.😠")
			return
		if count > 20:
			await self.bot.say("thats too many pings. stahp trying to break me.😠")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "pong "
		await self.bot.say(ping_string)

	@commands.command(pass_context=True)
	async def echo(self, ctx, *, message : str):
		"""Echo...

		I would hurl words into this darkness and wait for an echo, and if an echo sounded, no matter how faintly, I would send other words to tell, to march, to fight, to create a sense of the hunger for life that gnaws in us all"""
		await self.bot.say(message)

	@commands.command(pass_context=True)
	async def changelog(self, ctx):
		"""Gets a rough changelog for mangobyte

		Note that this is a very rough changelog built from git commit messages and so will sometimes not relate directly to your perspective.

		For more commit versions or better detailed information, check out the source on [GitHub](https://github.com/mdiller/MangoByte/commits/master)
		"""
		commit_url = "https://github.com/mdiller/MangoByte"
		description = f"For more information check out the [commit history]({commit_url}/commits/master) on GitHub\n"
		lines = get_changelog().split("\n")

		recent_date = 0

		for line in lines:
			if line == "":
				continue
			commit = line.split(",")
			full_sha = commit[0]
			timestamp = int(commit[1])
			small_sha = commit[2]
			message = ",".join(commit[3:])
			if timestamp > recent_date:
				recent_date = timestamp
			description += f"\n[`{small_sha}`]({commit_url}/commit/{full_sha}) {message}"

		if recent_date != 0:
			embed = discord.Embed(description=description, color=discord.Color.green(), timestamp=datetime.datetime.utcfromtimestamp(recent_date))
			embed.set_footer(text="Most recent change at")
		else:
			embed = discord.Embed(description=description, color=discord.Color.green())

		embed.set_author(name="Changelog", url=f"{commit_url}/commits/master")
		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def info(self, ctx):
		"""Prints info about mangobyte"""
		github = "https://github.com/mdiller/MangoByte"
		python_version = "[Python {}.{}.{}]({})".format(*os.sys.version_info[:3], "https://www.python.org/")
		discordpy = "https://github.com/Rapptz/discord.py"

		embed = discord.Embed(description="The juiciest unsigned 8 bit integer you eva gonna see", color=discord.Color.green())

		embed.set_author(name=ctx.message.channel.server.me.nick, icon_url=self.bot.user.avatar_url, url=github)

		embed.add_field(name="Development Info", value=(
			"Developed as an open source project, hosted on [GitHub]({}). "
			"Implemented using {} and a python discord api wrapper [discord.py]({})".format(github, python_version, discordpy)))

		embed.add_field(name="Features", value=(
			"• Answers questions (?ask)\n"
			"• Plays audio clips (?play, ?dota)\n"
			"• Greets users joining a voice channel\n"
			"• Reacts to things people say 😉\n"
			"• Is a slight bit sassy at times\n"
			"• For a full list of commands, try ?help"))

		owner = (await self.bot.application_info()).owner

		embed.set_footer(text="This MangoByte managed by {}".format(owner.name), icon_url=owner.avatar_url)

		await self.bot.say(embed=embed)

	@commands.command(pass_context=True)
	async def lasagna(self, ctx):
		"""A baked Italian dish

		Contains wide strips of pasta cooked and layered with meat or vegetables, cheese, and tomato sauce."""
		await self.bot.send_file(ctx.message.channel, settings.resourcedir + "images/lasagna.jpg")

	def __check(self, ctx):
		"""Checks to make sure the user has permissions"""
		if not ctx.message.channel.is_private:
			if botdata.serverinfo(ctx.message.server).is_banned(ctx.message.author):
				return False

		return True

	@checks.is_admin()
	@checks.is_not_PM()
	@commands.command(pass_context=True)
	async def botban(self, ctx, user: discord.User):
		"""Bans the user from using commands
		(Requires administrator privilages)"""
		if checks.is_owner_check(user):
			await self.bot.say("Ya can't ban mah owner, man. 😠")
			return
		if checks.is_admin_check(ctx.message.channel, user):
			await self.bot.say("Ya can't ban other admins")
			return
		if user == self.bot.user:
			await self.bot.say("Lol you can't ban me, silly")
			return
		botdata.serverinfo(ctx.message.server).botban(user)
		await self.bot.say("{} has henceforth been banned from using commands 😤".format(user.mention))

	@checks.is_admin()
	@checks.is_not_PM()
	@commands.command(pass_context=True)
	async def botunban(self, ctx, user: discord.User):
		"""Unbans the user, allowing them to use commands
		(Requires administrator privilages)"""
		if checks.is_owner_check(user) or user == self.bot.user:
			await self.bot.say("Ha ha. Very funny.")
			return
		botdata.serverinfo(ctx.message.server).botunban(user)
		await self.bot.say("{} is free of their restraints and may once again use commands".format(user.mention))

	@commands.command(pass_context=True)
	async def help(self, ctx, command : str=None):
		"""Shows this message."""
		def repl(obj):
			return _mentions_transforms.get(obj.group(0), '')

		# help by itself just lists our own commands.
		if command == "all":
			embed = self.bot.formatter.format_as_embed(ctx, self.bot, True)
		elif command == None:
			embed = self.bot.formatter.format_as_embed(ctx, self.bot, False)
		else:
			# try to see if it is a cog name
			name = _mention_pattern.sub(repl, command).lower()
			if name in map(lambda c: c.lower(), self.bot.cogs):
				for cog in self.bot.cogs:
					if cog.lower() == name:
						command = self.bot.cogs[cog]
			else:
				command = self.bot.commands.get(name)
				if command is None:
					await self.bot.send_message(ctx.message.channel, self.bot.command_not_found.format(name))
					return
			embed = self.bot.formatter.format_as_embed(ctx, command)

		await self.bot.send_message(ctx.message.channel, embed=embed)

	@commands.command(pass_context=True)
	async def scramble(self, ctx, *, message : str):
		"""Scrambles the insides of words"""

		def scramble_word(word):
			if len(word) < 4:
				letters = list(word)
				random.shuffle(letters)
				return "".join(letters)
			else:
				letters = list(word[1:-1])
				random.shuffle(letters)
				return word[0] + "".join(letters) + word[-1]

		results = []
		for word in message.split(" "):
			results.append(scramble_word(word))

		await self.bot.send_message(ctx.message.channel, " ".join(results))

	@commands.command(pass_context=True, hidden=True, aliases=["restapi"])
	async def restget(self, ctx, url):
		"""Gets a json response from a rest api and returns it"""
		async with aiohttp.get(url) as r:
			if r.status == 200:
				data = json.loads(await r.text(), object_pairs_hook=OrderedDict)
			else:
				raise UserError(f"Rest API call failed with status code: {r.status}")
		filename = "{}temp/{}.json".format(settings.resourcedir, "response")
		write_json(filename, data)
		await self.bot.send_file(ctx.message.channel, filename)
		os.remove(filename)



def setup(bot):
	bot.add_cog(General(bot))