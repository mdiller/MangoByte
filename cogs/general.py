import discord
from discord.ext import commands
from discord.ext.commands.bot import _mention_pattern, _mentions_transforms
from __main__ import settings, botdata, invite_link, httpgetter
from cogs.utils.helpers import *
from cogs.utils.botdata import UserInfo
from cogs.utils import checks, botdatatypes
from cogs.audio import AudioPlayerNotFoundError
from sqlalchemy import func
import cogs.utils.loggingdb as loggingdb
import string
import random
import datetime
import wikipedia
from bs4 import BeautifulSoup, Tag
from io import BytesIO
import re
import praw
import os
from .mangocog import *

def load_words():
	words = {}
	for root, dirs, files in os.walk(settings.resource("words/")):
		for file in files:
			with open(os.path.join(root, file), 'r') as f:
				text = f.read()
			key, ext = os.path.splitext(file)
			words[key] = text.split("\n")
	return words


# fills a template with the words of the type asked for
def fill_word_template(template, words):
	def replace(match):
		parts = match.group(1).split(":")
		keys = parts[0].split("|")
		values = []
		for key in keys:
			values += words[key]

		if len(parts) > 1:
			if "NOSPACE" in parts[1]:
				values = list(filter(lambda w: " " not in w, values))

		return random.choice(values)

	return re.sub(r"\{([^}]+)\}", replace, template)


class General(MangoCog):
	"""Basic and admin commands

	Random and/or fun commands with a variety of uses"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.donation_link = "https://www.paypal.me/dillerm"
		self.reactions = read_json(settings.resource("json/reactions.json"))
		self.questions = read_json(settings.resource("json/questions.json"))
		self.subscripts = read_json(settings.resource("json/subscripts.json"))
		self.superscripts = read_json(settings.resource("json/superscripts.json"))
		self.showerthoughts_data = read_json(settings.resource("json/showerthoughts.json"))
		self.words = load_words()

	@commands.command()
	async def userconfig(self, ctx, name, *, value = None):
		"""Configures the bot's user-specific settings

		Below are the different user-specific settings that you can tweak to customize mangobyte. You can get more information about a setting by typing `{cmdpfx}userconfig <settingname>`, and you can configure a setting by typing `{cmdpfx}userconfig <settingname> <value>`

		{userconfig_help}
		"""
		var = next((v for v in UserInfo.variables if v["key"] == name), None)
		if not var:
			vars_list = "\n".join(map(lambda v: f"`{v['key']}`", UserInfo.variables))
			await ctx.send(f"There is no userconfig setting called '{name}'. Try one of these:\n{vars_list}")
			return

		
		if not value: # We are just getting a value
			value = botdata.userinfo(ctx.message.author)[var["key"]]
			await ctx.send(embed=await botdatatypes.localize_embed(ctx, var, value, f"{self.cmdpfx(ctx)}userconfig"))
		else: # We are setting a value
			value = await botdatatypes.parse(ctx, var, value)
			botdata.userinfo(ctx.message.author)[var["key"]] = value
			await ctx.message.add_reaction("✅")

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

		cmdpfx = self.cmdpfx(ctx)
		embed.add_field(name="Features", value=(
			f"• Answers questions (`{cmdpfx}ask`)\n"
			f"• Plays audio clips (`{cmdpfx}play`, `{cmdpfx}dota`)\n"
			f"• Greets users joining a voice channel\n"
			f"• For a list of command categories, try `{cmdpfx}help`"))

		help_guild_link = "https://discord.gg/d6WWHxx"

		embed.add_field(name="Help", value=(
			f"If you want to invite mangobyte to your server/guild, click this [invite link]({invite_link}). "
			f"If you have a question, suggestion, or just want to try out mah features, check out the [Help Server/Guild]({help_guild_link})."))

		embed.add_field(name="Donate", value=(
			f"If you want to donate money to support MangoByte's server costs, click [here]({self.donation_link})"))

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
		embed.add_field(name="Registered Users", value="{:,}".format(len(list(filter(lambda user: user.steam, botdata.userinfo_list())))))

		commands = loggingdb_session.query(loggingdb.Message).filter(loggingdb.Message.command != None)
		commands_weekly = commands.filter(loggingdb.Message.timestamp > datetime.datetime.utcnow() - datetime.timedelta(weeks=1))
		embed.add_field(name="Commands", value=f"{commands.count():,}")
		embed.add_field(name="Commands (This Week)", value=f"{commands_weekly.count():,}")

		cmdpfx = self.cmdpfx(ctx)
		top_commands = loggingdb_session.query(loggingdb.Message.command, func.count(loggingdb.Message.command)).filter(loggingdb.Message.command != None).group_by(loggingdb.Message.command).order_by(func.count(loggingdb.Message.command).desc())
		if top_commands.count() >= 3:
			embed.add_field(name="Top Commands", value=(
				f"`{cmdpfx}{top_commands[0][0]}`\n"
				f"`{cmdpfx}{top_commands[1][0]}`\n"
				f"`{cmdpfx}{top_commands[2][0]}`\n"))

		top_commands_weekly = top_commands.filter(loggingdb.Message.timestamp > datetime.datetime.utcnow() - datetime.timedelta(weeks=1))
		if top_commands_weekly.count() >= 3:
			embed.add_field(name="Top Commands (This Week)", value=(
				f"`{cmdpfx}{top_commands_weekly[0][0]}`\n"
				f"`{cmdpfx}{top_commands_weekly[1][0]}`\n"
				f"`{cmdpfx}{top_commands_weekly[2][0]}`\n"))

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
	async def wiki(self, ctx, *, thing : str):
		"""Looks up a thing on wikipedia
		
		Uses the [python Wikipedia API](https://wikipedia.readthedocs.io/en/latest/) to look up a thing. 

		You can also try `{cmdpfx} wiki random` to get a random wiki page

		**Example:**
		`{cmdpfx}wiki potato`
		"""
		await ctx.channel.trigger_typing()

		def getWikiPage(title):
			try:
				if title == "random":
					return wikipedia.page(title=wikipedia.random(1), redirect=True, auto_suggest=True)
				return wikipedia.page(title=title, redirect=True, auto_suggest=True)
			except (wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.PageError) as e:
				if title == "random":
					return getWikiPage(title)
				if isinstance(e, wikipedia.exceptions.PageError) or len(e.options) == 0:
					raise UserError(f"Couldn't find anythin' fer \"*{thing}*\"")
				if e.options[0] == title:
					raise UserError("Can't find things on wiki for that")
				return getWikiPage(e.options[0])

		page = getWikiPage(thing)
		
		page_html = await httpgetter.get(page.url, "text")

		page_html = BeautifulSoup(page_html, 'html.parser')
		page_html = page_html.find(id="mw-content-text")

		def tagsToMarkdown(tag, plaintext=False):
			if isinstance(tag, list):
				result = ""
				for i in tag:
					result += tagsToMarkdown(i, plaintext)
				return result
			elif isinstance(tag, str):
				return tag
			elif isinstance(tag, Tag):
				if plaintext:
					return tagsToMarkdown(tag.contents, plaintext)
				elif tag.name == "b":
					return f"**{tagsToMarkdown(tag.contents)}**"
				elif tag.name == "i":
					return f"*{tagsToMarkdown(tag.contents)}*"
				elif tag.name in [ "sub", "sup" ]:
					if "reference" in tag.get("class", []):
						return "" # dont include references
					text = tagsToMarkdown(tag.contents, plaintext=True)
					if len(text) and text[0] == "[" and text[-1] == "]":
						return "" # this is a references thing you cant fool me
					replacements = self.subscripts if tag.name == "sub" else self.superscripts
					new_text = ""
					for c in text:
						new_text += replacements.get(c) if c in replacements else c
					return new_text
				elif tag.name == "a":
					if tag.get("href") is None:
						return tagsToMarkdown(tag.contents)
					if tag["href"].startswith("#"):
						return "" # dont include references
					href = re.sub("^/wiki/", "https://en.wikipedia.org/wiki/", tag['href'])
					href = re.sub(r"(\(|\))", r"\\\1", href)
					return f"[{tagsToMarkdown(tag.contents)}]({href})"
				else:
					# raise UserError(f"Unrecognized tag: {tag.name}")
					return tagsToMarkdown(tag.contents)
			
			return str(tag)

		summary = tagsToMarkdown(page_html.find("div").find(lambda tag: tag.name == "p" and not tag.attrs, recursive=False).contents)

		def markdownLength(text):
			text = re.sub(r"\[([^\[]*)]\([^\(]*\)", r"\1", text)
			return len(text)

		matches = re.finditer(r"([^\s\.]+\.)(\s|$)", summary)
		if matches:
			for match in list(matches):
				if markdownLength(summary[0:match.end()]) > 70:
					summary = summary[0:match.end()]
					break

		embed = discord.Embed(description=summary)
		embed.title = f"**{page.title}**"
		embed.url = page.url

		for image in page_html.find_all(class_="navbox"):
			image.decompose()
		for image in page_html.find_all(class_="mbox-image"):
			image.decompose()
		for image in page_html.find_all(class_="metadata plainlinks stub"):
			image.decompose()

		page_html_text = page_html.prettify()

		best_image = None
		best_image_index = -1
		for image in page.images:
			if "Wikisource-logo" in image:
				continue
			if re.search(r"\.(png|jpg|jpeg|gif)$", image, re.IGNORECASE):
				index = page_html_text.find(image.split('/')[-1])
				if index != -1 and (best_image_index == -1 or index < best_image_index):
					best_image = image
					best_image_index = index

		if best_image:
			embed.set_image(url=best_image)

		embed.set_footer(text="Retrieved from Wikipedia", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Wikipedia's_W.svg/2000px-Wikipedia's_W.svg.png")

		if best_image and re.search(r"\.svg$", best_image, re.IGNORECASE):
			await ctx.send(embed=embed, file=svg_png_image)
		else:
			await ctx.send(embed=embed)

	@commands.command()
	async def reddit(self, ctx, url_or_id):
		"""Gets a reddit submission and returns a nice embed of it"""
		if settings.reddit is None:
			raise UserError("This MangoByte has not been configured to get reddit submissions. Gotta add your info to `settings.json`")

		await ctx.channel.trigger_typing()

		reddit = praw.Reddit(client_id=settings.reddit["client_id"],
			client_secret=settings.reddit["client_secret"],
			user_agent=settings.reddit["user_agent"])

		try:
			if re.search(r"(redd\.it|reddit.com)", url_or_id):
				if not re.search(r"https?://", url_or_id):
					url_or_id = "http://" + url_or_id
				submission = reddit.submission(url=url_or_id)
			else:
				submission = reddit.submission(id=url_or_id)
			description = submission.selftext
		except:
			raise UserError("Couldn't properly find that reddit submission")

		character_limit = 600
		# convert between markdown types
		description = re.sub(r"\n(?:\*|-) (.*)", r"\n• \1", description)
		description = re.sub(r"(?:^|\n)#+([^#\n]+)\n", r"\n__**\1**__ \n", description)
		description = re.sub(r"\n+---\n+", r"\n\n", description)
		description = re.sub(r"&nbsp;", r" ", description)

		if len(description) > character_limit:
			description = f"{description[0:character_limit]}...\n[Read More]({submission.shortlink})"

		embed = discord.Embed(description=description, color=discord.Color(int("ff4500", 16)))
		embed.set_footer(text=f"/r/{submission.subreddit}", icon_url="https://images-na.ssl-images-amazon.com/images/I/418PuxYS63L.png")

		embed.title = submission.title
		embed.url = submission.shortlink

		url_ext = submission.url.split(".")[-1]

		if url_ext in ["gifv", "gif", "png", "jpg", "jpeg"]:
			image_url = submission.url
			if url_ext == "gifv":
				image_url = image_url.replace(".gifv", ".gif")
			embed.set_image(url=image_url)

		await ctx.send(embed=embed)

	@commands.command(aliases=["quote", "showerthoughts", "thought" ])
	async def showerthought(self, ctx):
		"""Gets a top post from r/ShowerThoughts
		
		Gets a random post from the [r/ShowerThoughts](https://www.reddit.com/r/Showerthoughts/top/?sort=top&t=all) subreddit. Looks through the list of the all time top posts for the subreddit
		"""
		await ctx.channel.trigger_typing()

		thought = random.choice(self.showerthoughts_data)

		author = thought["author"]
		author = f"u/{author}" if author else "[deleted]"

		embed = discord.Embed()

		embed.description = thought["title"]
		embed.timestamp = datetime.datetime.utcfromtimestamp(thought["timestamp"])
		embed.set_footer(text=author)

		await ctx.send(embed=embed)

	@commands.command(hidden=True, aliases=["restapi"])
	async def restget(self, ctx, url):
		"""Gets a json response from a rest api and returns it"""
		await ctx.channel.trigger_typing()
		data = await httpgetter.get(url)

		filename = settings.resource("temp/response.json")
		write_json(filename, data)
		await ctx.send(file=discord.File(filename))
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

	@commands.command()
	async def insult(self, ctx):
		"""Gets a nice insult for ya

		Mention someone in discord and I'll insult them instead of you

		**Example:**
		`{cmdpfx}insult`
		`{cmdpfx}insult @InnocentMan`
		"""
		start = "You "
		start_local = start

		template = "{animal|food|furniture|instrument:NOSPACE}-{body_part_ed} {relation} of a {animal|furniture}"

		if ctx.message.mentions:
			user = ctx.message.mentions[0]
			if user.id == ctx.guild.me.id:
				template = "lovely fellow"
			start = f"{user.mention}, you're a "
			start_local = f"{user.name}, you're a "

		result = fill_word_template(template, self.words)

		await ctx.send(start + result)
		if ctx.guild.me.voice:
			await self.play_clip(f"tts:{start_local}{result}", ctx)
		

	async def on_message(self, message):
		if message.guild is not None and not botdata.guildinfo(message.guild.id).reactions:
			return

		if (message.author == self.bot.user) or message.content.startswith(self.cmdpfx(message.guild)):
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
		msg = loggingdb.insert_message(ctx.message, ctx.command.name, loggingdb_session)
		loggingdb.insert_command(ctx, loggingdb_session)
		print(msg)

	async def on_command_completion(self, ctx):
		loggingdb.command_finished(ctx, "completed", None, loggingdb_session)

	async def on_guild_join(self, guild):
		loggingdb.update_guilds(self.bot.guilds, loggingdb_session)

	async def on_guild_remove(self, guild):
		loggingdb.update_guilds(self.bot.guilds, loggingdb_session)

	@commands.command(aliases=[ "tipjar", "donation" ])
	async def donate(self, ctx):
		"""Posts the donation information"""
		embed = discord.Embed()

		embed.description = "I host MangoByte on [DigitalOcean](https://www.digitalocean.com), which costs `$15` per month. (2nd row in the 'Flexible Droplet' table [here](https://www.digitalocean.com/pricing/)). "
		embed.description += "I have a decently paying job, so MangoByte won't be going down anytime soon, but if you want to help with the server costs, or just support me because you feel like it, feel free to donate using the link below:"
		embed.description += f"\n\n[Donation Link]({self.donation_link})"

		await ctx.send(embed=embed)


def setup(bot):
	bot.add_cog(General(bot))