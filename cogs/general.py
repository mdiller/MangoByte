import discord
from discord.ext import commands
from discord.ext.commands.bot import _mention_pattern, _mentions_transforms
from __main__ import settings, botdata, invite_link, httpgetter, loggingdb_session
from cogs.utils.helpers import *
from cogs.utils import checks
from cogs.audio import AudioPlayerNotFoundError
from sqlalchemy import func
import cogs.utils.loggingdb as loggingdb
import string
import random
import datetime
import wikipedia
from bs4 import BeautifulSoup, Tag
import re
from .mangocog import *


class General(MangoCog):
	"""Basic and admin commands

	Random and/or fun commands with a variety of uses"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.reactions = read_json(settings.resource("json/reactions.json"))
		self.questions = read_json(settings.resource("json/questions.json"))

	@commands.command()
	async def ping(self, ctx, count : int=1):
		"""Pongs a number of times(within reason)

		Pongs... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await ctx.send("thats not enough pings. stahp trying to break me.😠")
			return
		if count > 20:
			await ctx.send("thats too many pings. stahp trying to break me.😠")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "pong "
		await ctx.send(ping_string)

	@commands.command()
	async def echo(self, ctx, *, message : str):
		"""Echo...

		I would hurl words into this darkness and wait for an echo, and if an echo sounded, no matter how faintly, I would send other words to tell, to march, to fight, to create a sense of the hunger for life that gnaws in us all"""
		await ctx.send(message)

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
		await ctx.send(embed=embed)

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

		help_guild_link = "https://discord.gg/d6WWHxx"

		embed.add_field(name="Help", value=(
			f"If you want to invite mangobyte to your server/guild, click this [invite link]({invite_link}). "
			f"If you have a question, suggestion, or just want to try out mah features, check out the [Help Server/Guild]({help_guild_link})."))

		owner = (await self.bot.application_info()).owner

		embed.set_footer(text="MangoByte developed by {}".format(owner.name), icon_url=owner.avatar_url)

		await ctx.send(embed=embed)

	@commands.command()
	async def invite(self, ctx):
		"""Prints the invite link"""
		await ctx.send(invite_link)

	@commands.command()
	async def botstats(self, ctx):
		"""Displays some bot statistics"""
		embed = discord.Embed(color=discord.Color.green())

		embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)

		embed.add_field(name="Servers/Guilds", value="{:,}".format(len(self.bot.guilds)))
		embed.add_field(name="Registered Users", value="{:,}".format(len(list(filter(lambda user: user.steam32, botdata.userinfo_list())))))

		commands = loggingdb_session.query(loggingdb.Message).filter(loggingdb.Message.command != None)
		commands_weekly = commands.filter(loggingdb.Message.timestamp > datetime.datetime.utcnow() - datetime.timedelta(weeks=1))
		embed.add_field(name="Commands", value=f"{commands.count():,}")
		embed.add_field(name="Commands (This Week)", value=f"{commands_weekly.count():,}")


		top_commands = loggingdb_session.query(loggingdb.Message.command, func.count(loggingdb.Message.command)).filter(loggingdb.Message.command != None).group_by(loggingdb.Message.command).order_by(func.count(loggingdb.Message.command).desc())
		if top_commands.count() >= 3:
			embed.add_field(name="Top Commands", value=(
				f"`?{top_commands[0][0]}`\n"
				f"`?{top_commands[1][0]}`\n"
				f"`?{top_commands[2][0]}`\n"))

		top_commands_weekly = top_commands.filter(loggingdb.Message.timestamp > datetime.datetime.utcnow() - datetime.timedelta(weeks=1))
		if top_commands_weekly.count() >= 3:
			embed.add_field(name="Top Commands (This Week)", value=(
				f"`?{top_commands_weekly[0][0]}`\n"
				f"`?{top_commands_weekly[1][0]}`\n"
				f"`?{top_commands_weekly[2][0]}`\n"))

		await ctx.send(embed=embed)

	@commands.command()
	async def lasagna(self, ctx):
		"""A baked Italian dish

		Contains wide strips of pasta cooked and layered with meat or vegetables, cheese, and tomato sauce."""
		await ctx.send(file=discord.File(settings.resource("images/lasagna.jpg")))

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
					await ctx.send(self.bot.command_not_found.format(name))
					return
			embed = await self.bot.formatter.format_as_embed(ctx, command)

		await ctx.send(embed=embed)

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

		await ctx.send(" ".join(results))

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
		
		page_html = await httpgetter.get(page.url, "text")

		soup = BeautifulSoup(page_html, 'html.parser')

		def tagsToMarkdown(tag):
			if isinstance(tag, list):
				result = ""
				for i in tag:
					result += tagsToMarkdown(i)
				return result
			elif isinstance(tag, str):
				return tag
			elif isinstance(tag, Tag):
				if tag.name == "b":
					return f"**{tagsToMarkdown(tag.contents)}**"
				elif tag.name == "i":
					return f"*{tagsToMarkdown(tag.contents)}*"
				elif tag.name == "a":
					return f"[{tagsToMarkdown(tag.contents)}]({tag['href']})"
				else:
					# raise ValueError(f"Unrecognized tag: {tag.name}")
					return tagsToMarkdown(tag.contents)
			
			return str(tag)

		summary = tagsToMarkdown(soup.find(id="mw-content-text").find("p").contents)

		sentances = summary.split(".")
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

		await ctx.send(embed=embed)

	@commands.command(hidden=True, aliases=["restapi"])
	async def restget(self, ctx, url):
		"""Gets a json response from a rest api and returns it"""
		await ctx.channel.trigger_typing()
		data = await httpgetter.get(url)

		filename = settings.resource("temp/response.json")
		write_json(filename, data)
		await ctx.send(discord.File(filename))
		os.remove(filename)

	@commands.command()
	async def ask(self, ctx, *, question : str=""):
		"""Answers any question you might have"""
		random.seed(question)
		for check in self.questions:
			if re.search(check["regex"], question):
				clip = await self.get_clip(f"dota:{random.choice(check['responses'])}", ctx)
				await ctx.send(clip.text)
				try:
					await self.play_clip(clip, ctx)
				except AudioPlayerNotFoundError:
					pass # Not needed for this 
				return
		print("didnt match anything for ask")
		

	async def on_message(self, message):
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

	async def on_command(self, ctx):
		msg = loggingdb.convert_message(ctx)
		loggingdb_session.add(msg)
		loggingdb_session.commit()
		print(msg)



def setup(bot):
	bot.add_cog(General(bot))