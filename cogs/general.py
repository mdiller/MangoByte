import discord
from discord.ext import commands
from discord.ext.commands.bot import _mention_pattern, _mentions_transforms
from __main__ import settings, botdata
from cogs.utils.helpers import *
from cogs.utils import checks
from cogs.audio import AudioPlayerNotFoundError
import asyncio
import aiohttp
import string
import random
import datetime
import wikipedia
import re
from .mangocog import *


class General(MangoCog):
	"""Basic and admin commands

	These commands are primarily used to stop people from ruining things"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.reactions = read_json(settings.resource("json/reactions.json"))
		self.questions = read_json(settings.resource("json/questions.json"))

	@commands.command()
	async def ping(self, ctx, count : int=1):
		"""Pongs a number of times(within reason)

		Pongs... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await ctx.channel.send("thats not enough pings. stahp trying to break me.😠")
			return
		if count > 20:
			await ctx.channel.send("thats too many pings. stahp trying to break me.😠")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "pong "
		await ctx.channel.send(ping_string)

	@commands.command()
	async def echo(self, ctx, *, message : str):
		"""Echo...

		I would hurl words into this darkness and wait for an echo, and if an echo sounded, no matter how faintly, I would send other words to tell, to march, to fight, to create a sense of the hunger for life that gnaws in us all"""
		await ctx.channel.send(message)

	@commands.command()
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
		await ctx.channel.send(embed=embed)

	@commands.command()
	async def info(self, ctx):
		"""Prints info about mangobyte"""
		github = "https://github.com/mdiller/MangoByte"
		python_version = "[Python {}.{}.{}]({})".format(*os.sys.version_info[:3], "https://www.python.org/")
		discordpy = "https://github.com/Rapptz/discord.py"

		embed = discord.Embed(description="The juiciest unsigned 8 bit integer you eva gonna see", color=discord.Color.green())

		embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url, url=github)

		embed.add_field(name="Development Info", value=(
			"Developed as an open source project, hosted on [GitHub]({}). "
			"Implemented using {} and a python discord api wrapper [discord.py]({})".format(github, python_version, discordpy)))

		embed.add_field(name="Features", value=(
			"• Answers questions (`?ask`)\n"
			"• Plays audio clips (`?play`, `?dota`)\n"
			"• Greets users joining a voice channel\n"
			"• For a list of command categories, try `?help`"))

		invite_link = "https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot&client_id=213476188037971968"
		help_guild_link = "https://discord.gg/d6WWHxx"

		embed.add_field(name="Help", value=(
			f"If you want to invite mangobyte to your server/guild, click this [invite link]({invite_link}). "
			f"If you have a question, suggestion, or just want to try out mah features, check out the [Help Server/Guild]({help_guild_link})."))

		owner = (await self.bot.application_info()).owner

		embed.set_footer(text="This MangoByte managed by {}".format(owner.name), icon_url=owner.avatar_url)

		await ctx.channel.send(embed=embed)

	@commands.command()
	async def lasagna(self, ctx):
		"""A baked Italian dish

		Contains wide strips of pasta cooked and layered with meat or vegetables, cheese, and tomato sauce."""
		await ctx.channel.send(file=discord.File(settings.resource("images/lasagna.jpg")))

	def __global_check(self, ctx):
		"""Checks to make sure the user has permissions"""
		if not isinstance(ctx.message.channel, discord.abc.PrivateChannel):
			if botdata.guildinfo(ctx.message.guild).is_banned(ctx.message.author):
				return False

		return True

	@checks.is_admin()
	@checks.is_not_PM()
	@commands.command()
	async def botban(self, ctx, user: discord.Member):
		"""Bans the user from using commands
		(Requires administrator privilages)"""
		if checks.is_owner_check(user):
			await ctx.channel.send("Ya can't ban mah owner, man. 😠")
			return
		if checks.is_admin_check(ctx.message.channel, user):
			await ctx.channel.send("Ya can't ban other admins")
			return
		if user == self.bot.user:
			await ctx.channel.send("Lol you can't ban me, silly")
			return
		botdata.guildinfo(ctx.message.guild).botban(user)
		await ctx.channel.send("{} has henceforth been banned from using commands 😤".format(user.mention))

	@checks.is_admin()
	@checks.is_not_PM()
	@commands.command()
	async def botunban(self, ctx, user: discord.Member):
		"""Unbans the user, allowing them to use commands
		(Requires administrator privilages)"""
		if checks.is_owner_check(user) or user == self.bot.user:
			await ctx.channel.send("Ha ha. Very funny.")
			return
		botdata.guildinfo(ctx.message.guild).botunban(user)
		await ctx.channel.send("{} is free of their restraints and may once again use commands".format(user.mention))

	@commands.command()
	async def help(self, ctx, command : str=None):
		"""Shows this message."""
		def repl(obj):
			return _mentions_transforms.get(obj.group(0), '')

		# help by itself just lists our own commands.
		if command == "all":
			embed = await self.bot.formatter.format_as_embed(ctx, self.bot, True)
		elif command == None:
			embed = await self.bot.formatter.format_as_embed(ctx, self.bot, False)
		else:
			# try to see if it is a cog name
			name = _mention_pattern.sub(repl, command).lower()
			if name in map(lambda c: c.lower(), self.bot.cogs):
				for cog in self.bot.cogs:
					if cog.lower() == name:
						command = self.bot.cogs[cog]
			else:
				command = self.bot.all_commands.get(name)
				if command is None:
					await ctx.channel.send(self.bot.command_not_found.format(name))
					return
			embed = await self.bot.formatter.format_as_embed(ctx, command)

		await ctx.channel.send(embed=embed)

	@commands.command()
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

		await ctx.channel.send(" ".join(results))

	@commands.command(aliases=["define", "lookup", "wikipedia", "whatis"])
	async def wiki(self, ctx, *, query : str):
		"""Looks up a thing on wikipedia
		
		Uses the [python Wikipedia API](https://wikipedia.readthedocs.io/en/latest/) to look up a thing. 

		This api is a wrapper for the [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page), which is applicable to Wikipedia because Wikipedia is build ontop of MediaWiki
		"""
		await ctx.channel.trigger_typing()

		def getWikiPage(title):
			try:
				return wikipedia.page(title=title, redirect=True, auto_suggest=True)
			except (wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.PageError) as e:
				if isinstance(e, wikipedia.exceptions.PageError) or len(e.options) == 0:
					raise UserError(f"Couldn't find anythin' fer \"*{query}*\"")
				return getWikiPage(e.options[0])

		page = getWikiPage(query)

		
		async with aiohttp.ClientSession() as session:
			async with session.get(page.url) as r:
				if r.status == 200:
					page_html = await r.text()

		sentances = page.summary.split(".")
		summary = sentances[0]
		for i in range(1, len(sentances)):
			# If this sentence is acutally a part of the last sentence OR our summary isn't long enough
			if not re.search(r"^ [a-z]", sentances[i]) and len(summary) > 50:
				break
			summary += "." + sentances[i]
		summary += "."

		embed = discord.Embed(description=summary)
		embed.set_author(name=page.title, url=page.url)

		best_image = None
		best_image_index = -1
		for image in page.images:
			if re.search("\.(png|jpg|jpeg|gif)$", image, re.IGNORECASE):
				index = page_html.find(image.split('/')[-1])
				if (best_image_index == -1) or (index != -1 and index < best_image_index):
					best_image = image
					best_image_index = index
		if best_image:
			embed.set_image(url=best_image)

		embed.set_footer(text="Retrieved from Wikipedia", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Wikipedia's_W.svg/2000px-Wikipedia's_W.svg.png")

		await ctx.channel.send(embed=embed)

	@commands.command(hidden=True, aliases=["restapi"])
	async def restget(self, ctx, url):
		"""Gets a json response from a rest api and returns it"""
		await ctx.channel.trigger_typing()
		async with aiohttp.ClientSession() as session:
			async with session.get(url) as r:
				if r.status == 200:
					data = json.loads(await r.text(), object_pairs_hook=OrderedDict)
				else:
					raise UserError(f"Rest API call failed with status code: {r.status}")
		filename = settings.resource("temp/response.json")
		write_json(filename, data)
		await ctx.channel.send(discord.File(filename))
		os.remove(filename)

	@commands.command()
	async def ask(self, ctx, *, question : str=""):
		"""Answers any question you might have"""
		random.seed(question)
		for check in self.questions:
			if re.search(check["regex"], question):
				clip = await self.get_clip(f"dota:{random.choice(check['responses'])}")
				await ctx.channel.send(clip.text)
				try:
					await self.play_clip(clip, ctx)
				except AudioPlayerNotFoundError:
					pass # Not needed for this 
				return
		print("didnt match anything for ask")
		

	async def on_message(self, message):
		if message.content.startswith("?"):
			await self.log_message(message)

		if message.guild is not None and not botdata.guildinfo(message.guild.id).reactions:
			return

		if (message.author == self.bot.user) or message.content.startswith("?"):
			return

		random.seed(message.content)

		for check in self.reactions:
			expression = check["regex"]
			if check.get("word"):
				expression = "\\b({})\\b".format(expression)
				match = re.search(expression, message.clean_content, re.IGNORECASE)
			else:
				match = re.search(expression, message.clean_content)
			if match and (random.random() < check.get("chance", 1.0)):
				await message.add_reaction(random.choice(check["reaction"]))
				break

def setup(bot):
	bot.add_cog(General(bot))