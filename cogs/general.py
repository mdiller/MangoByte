import discord
from discord.ext import commands, tasks
from __main__ import settings, botdata, invite_link, httpgetter, loggingdb
from cogs.utils.helpers import *
from cogs.utils.botdata import UserInfo
from cogs.utils import checks, botdatatypes, wikipedia
from cogs.audio import AudioPlayerNotFoundError
from sqlalchemy import func
from collections import OrderedDict
import json
import string
import random
import datetime
import html
from bs4 import BeautifulSoup, Tag
from io import BytesIO
import re
import praw
import os
from .mangocog import *

donate_links = {
	"Patreon": "https://www.patreon.com/dillerm",
	"BuyMeACoffee": "https://www.buymeacoffee.com/dillerm",
	"Ko-fi": "https://ko-fi.com/dillerm",
	"PayPal": "https://www.paypal.me/dillerm"
}

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

# loads a markdown file as a dictionary
def load_md_as_dict(filename):
	with open(filename, "r") as f:
		text = f.read()
	result = {}
	pattern = re.compile(r"\n# ([^\n]+)\n([\s\S]*?)(?=\n# |$)")
	for match in pattern.finditer(text):
		name = match.group(1).strip()
		description = match.group(2).strip()
		description = re.sub("\n`", u"\n\u200b`", description)
		result[name] = description
	return result

class General(MangoCog):
	"""Commands that don't really fit into the other categories

	Random and/or fun commands with a variety of uses"""
	def __init__(self, bot):
		MangoCog.__init__(self, bot)
		self.donation_link = "https://www.paypal.me/dillerm"
		self.reactions = read_json(settings.resource("json/reactions.json"))
		self.questions = read_json(settings.resource("json/questions.json"))
		self.subscripts = read_json(settings.resource("json/subscripts.json"))
		self.superscripts = read_json(settings.resource("json/superscripts.json"))
		self.showerthoughts_data = read_json(settings.resource("json/showerthoughts.json"))
		self.docs_data = load_md_as_dict(settings.resource("docs.md"))
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

		help_guild_link = "https://discord.gg/d6WWHxx"

		embed.add_field(name="Help", value=(
			f"If you want to invite mangobyte to your server/guild, click this [invite link]({invite_link}). "
			f"If you have a question, suggestion, or just want to try out mah features, check out the [Help Server/Guild]({help_guild_link})."))

		cmdpfx = self.cmdpfx(ctx)
		embed.add_field(name="Features", value=(
			f"• Answers questions (`{cmdpfx}ask`)\n"
			f"• Plays audio clips (`{cmdpfx}play`, `{cmdpfx}dota`)\n"
			f"• Greets users joining a voice channel\n"
			f"• For a list of command categories, try `{cmdpfx}help`"), inline=False)

		donate_stuff = "\n".join(map(lambda key: f"• [{key}]({donate_links[key]})", donate_links))
		embed.add_field(name="Donating", value=(
			f"If you want to donate money to support MangoByte's server costs, click one of the links below. If you want to learn more about how much I spend on MangoByte per month try `{cmdpfx}donate`.\n{donate_stuff}"))

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
		await ctx.channel.trigger_typing()

		embed = discord.Embed(color=discord.Color.green())

		embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)

		embed.add_field(name="Servers/Guilds", value="{:,}".format(len(self.bot.guilds)))
		embed.add_field(name="Registered Users", value="{:,}".format(botdata.count_users_with_key("steam")))

		thisweek = "timestamp between datetime('now', '-7 days') AND datetime('now', 'localtime')"
		query_results = await loggingdb.query_multiple([
			f"select count(*) from messages where command is not null",
			f"select count(*) from messages where command is not null and {thisweek}",
			f"select command from messages where command is not null group by command order by count(command) desc limit 3",
			f"select command from messages where command is not null and {thisweek} group by command order by count(command) desc limit 3"
		])


		# embed.add_field(name="Commands", value=f"{query_results[0][0][0]:,}")
		embed.add_field(name="Commands (This Week)", value=f"{query_results[1][0][0]:,}")

		cmdpfx = self.cmdpfx(ctx)
		top_commands = query_results[2]
		# if len(top_commands) >= 3:
		# 	embed.add_field(name="Top Commands", value=(
		# 		f"`{cmdpfx}{top_commands[0][0]}`\n"
		# 		f"`{cmdpfx}{top_commands[1][0]}`\n"
		# 		f"`{cmdpfx}{top_commands[2][0]}`\n"))

		top_commands_weekly = query_results[3]
		if len(top_commands_weekly) >= 3:
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
		
		Uses my own implementation of the [Wikipedia API](https://www.mediawiki.org/wiki/API:Tutorial)

		You can also try `{cmdpfx}wiki random` to get a random wiki page
		
		Note that I've had to remove the images from these (unless you're in a NSFW channel) because I have no way of checking if it is an NSFW image, and posting an NSFW image in non-NSFW channels would be against discord's ToS. Sorry about that!

		**Example:**
		`{cmdpfx}wiki potato`
		"""
		await ctx.channel.trigger_typing()

		page = await wikipedia.get_wikipedia_page(thing)

		embed = discord.Embed(description=page.markdown)
		embed.title = f"**{page.title}**"
		embed.url = page.url

		footer_text = "Retrieved from Wikipedia"

		if page.image:
			if (not isinstance(ctx.channel, discord.DMChannel)) and ctx.channel.is_nsfw():
				embed.set_image(url=page.image)
			else:
				footer_text += ". (Image omitted because I can't check if it is NSFW) D:"

		embed.set_footer(text=footer_text, icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Wikipedia's_W.svg/2000px-Wikipedia's_W.svg.png")
		
		await ctx.send(embed=embed)

	@commands.command()
	async def reddit(self, ctx, url_or_id):
		"""Displays a formatted reddit post

		Note that this will only get nsfw posts if you call this in an nsfw channel"""
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

		
		if submission.over_18:
			if (isinstance(ctx.channel, discord.DMChannel)) or (not ctx.channel.is_nsfw()):
				raise UserError("That is an NSFW post, so I can't link it in this non-nsfw channel.")


		character_limit = 600
		# convert between markdown types
		description = re.sub(r"\n(?:\*|-) (.*)", r"\n• \1", description)
		description = re.sub(r"(?:^|\n)#+([^#\n]+)\n", r"\n__**\1**__ \n", description)
		description = re.sub(r"\n+---\n+", r"\n\n", description)
		description = re.sub(r"&nbsp;", r" ", description)

		description = html.unescape(description)

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
				clip = await self.get_clip(random.choice(check['responses']), ctx)
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
		if ctx.guild and ctx.guild.me.voice:
			await self.play_clip(f"tts:{start_local}{result}", ctx)
		
	
	@commands.command(aliases=["random"])	
	async def random_number(self, ctx, maximum : int, minimum : int = 0):
		"""Gets a random number between the minimum and maximum

		The min and max integer bounds are **inclusive**

		The command will be able to figure out which number is the minimum and which is the maximum if they are put in backwards. If one number is entered, it is assumed to be the maximum, and the default minimum is 0

		**Example:**
		`{cmdpfx}random 5`
		`{cmdpfx}random 1 10`
		"""
		result = None
		if maximum < minimum:
			result = random.randint(maximum, minimum)
		else:
			result = random.randint(minimum, maximum)
		await ctx.send(result)
	
	@commands.command(aliases=["pickone"])
	async def choose(self, ctx, *options):
		"""Randomly chooses one of the given options

		You must provide at least one option for the bot to choose, and the options should be separated by spaces
		
		**Example:**
		`{cmdpfx}choose Dota2 Fortnite RocketLeague`
		`{cmdpfx}choose green red blue`
		"""
		if not len(options) > 0:
			raise UserError("You gotta give me a couple different options, separated by spaces")
		await ctx.send(random.choice(options))

	@commands.command(aliases=["documentation"])
	async def docs(self, ctx, *, topic : str = None):
		"""Shows the documentation for the given topic

		If no parameters are given, then this shows the available documentation
		
		**Example:**
		`{cmdpfx}docs`
		`{cmdpfx}docs Match Filter`
		`{cmdpfx}docs matchfilter`
		"""
		if topic is None:
			embed = discord.Embed()
			embed.title = "Available Topics"
			embed.description = "\n".join(map(lambda name: f"• {name}", list(self.docs_data.keys())))
			await ctx.send(embed=embed)
			return
		clean_topic = topic.lower().replace(" ", "")
		found_topic = None
		for name in self.docs_data:
			simple_name = name.lower().replace(" ", "")
			if clean_topic in simple_name:
				found_topic = name
				break
		if found_topic is None:
			raise UserError(f"Couldn't find a topic called '{topic}'")

		embed = discord.Embed()
		embed.title = found_topic
		embed.description = self.docs_data[found_topic]
		await ctx.send(embed=embed)

	@tasks.loop(hours=12)
	async def update_topgg(self):
		print("update_topgg() entered")
		if settings.debug or (settings.topgg is None):
			return # nothing to do here

		bot_id = self.bot.user.id
		topgg_token = settings.topgg
		guilds_count = len(self.bot.guilds)

		try:
			url = f"https://top.gg/api/bots/{bot_id}/stats"
			body = {
				"server_count": guilds_count
			}
			headers = {
				"Authorization": topgg_token
			}
			response = await httpgetter.post(url, body=body, headers=headers)
		except HttpError as e:
			await self.send_owner(f"Updating top.gg failed with {e.code} error")

	@tasks.loop(hours=12)
	async def do_infodump(self):
		print("do_infodump() entered")
		if not settings.infodump_path:
			return # nothing to do here

		guilds_count = len(self.bot.guilds)
		member_count = botdata.count_users_with_key("steam")

		data = {
			"servers": guilds_count,
			"registered_users": member_count
		}
		try:
			with open(settings.infodump_path, "w+") as f:
				f.write(json.dumps(data))
		except Exception as e:
			await self.send_owner(f"do_infodump failed w/ exception: {e}")

	@tasks.loop(minutes=5)
	async def check_dota_patch(self):
		print("check_dota_patch() entered")
		url = "https://www.dota2.com/patches/"
		try:
			text = await httpgetter.get(url, return_type="text")
		except HttpError as e:
			await self.send_owner(f"patches update failed the check with a http {e.code} error")
			return # failed, so return
		except Exception as e:
			await self.send_owner(f"patches update failed the check w/ exception: {e}")
			return # failed, so return
		soup = BeautifulSoup(text, "html.parser")

		current_patch = soup.find(name="title").contents[0]
		old_patch = botdata["dotapatch"]

		if old_patch == current_patch:
			return # thats the current patch, do nothing
		if current_patch.strip() == "Gameplay Update":
			return # thats what happens when theyre tryna switch it and theyre in the process, so give it a minute and try again later
		print(f"\"{current_patch}\"")
		print(current_patch == "Gameplay Update")
		print(str(current_patch) == "Gameplay Update")
		await self.send_owner(f"patches update triggered: (new one is '{current_patch}', old one was '{old_patch}')")
		botdata["dotapatch"] = current_patch

		def count_class_in_id(element_id, classname):
			element = soup.find(id=element_id)
			if element is None:
				return 0
			return len(element.find_all(lambda tag: tag.get("class") == [ classname ]))

		description = ""
		section_counts = OrderedDict()
		section_counts["General"] = count_class_in_id("GeneralSection", "PatchNote")
		section_counts["Item"] = count_class_in_id("ItemsSection", "ItemName")
		section_counts["Hero"] = count_class_in_id("HeroesSection", "HeroName")
		for section in section_counts:
			count = section_counts[section]
			if count > 0:
				description += f"\n{count} {section} changes"

		image_meta_tag = soup.find(name="meta", attrs={ "property" : "og:image" })

		if image_meta_tag is not None:
			description = ""

		if description == "" and image_meta_tag is None:
			description = "*Couldn't parse the changes.*"

		# we can improve this embed later but for now this is what we got
		embed = discord.Embed(timestamp=datetime.datetime.utcnow())
		embed.title = current_patch
		embed.url = url
		embed.description = description
		embed.set_thumbnail(url="https://cdn.cloudflare.steamstatic.com/apps/dota2/images/blog/play/dota_logo.png")
		if image_meta_tag:
			embed.set_image(url=image_meta_tag["content"])

		messageables = []
		guildinfos = botdata.guildinfo_list()
		for guildinfo in guildinfos:
			if guildinfo.dotapatchchannel is not None:
				channel = self.bot.get_channel(guildinfo.dotapatchchannel)
				if channel is not None:
					messageables.append(channel)
				else:
					print(f"couldn't find channel {guildinfo.dotapatchchannel} when announcing dota patches")

		userinfos = botdata.userinfo_list()
		for userinfo in userinfos:
			if userinfo.dmdotapatch:
				user = self.bot.get_user(userinfo.discord)
				if user is not None:
					messageables.append(user)
				else:
					print(f"couldn't find user {userinfo.discord} when announcing dota patches")

		tasks = []
		for messageable in messageables:
			tasks.append(messageable.send(embed=embed))

		bundler = AsyncBundler(tasks)
		print("waiting for dota patch bundle to complete")
		await bundler.wait()
		print("dota patch bundle completed")
		await self.send_owner("__Dota Patch Sent!__\n" + bundler.status_as_string())


	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author.bot and settings.debug:
			ctx = await self.bot.get_context(message)
			await self.bot.invoke(ctx)
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

	@commands.Cog.listener()
	async def on_command(self, ctx):
		msg = await loggingdb.insert_message(ctx.message, ctx.command.name)
		await loggingdb.insert_command(ctx)
		print(msg)

	@commands.Cog.listener()
	async def on_command_completion(self, ctx):
		await loggingdb.command_finished(ctx, "completed", None)

	@commands.Cog.listener()
	async def on_guild_join(self, guild):
		await loggingdb.update_guilds(self.bot.guilds)

	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		await loggingdb.update_guilds(self.bot.guilds)

	@commands.command(aliases=[ "tipjar", "donation" ])
	async def donate(self, ctx):
		"""Posts the donation information"""
		embed = discord.Embed()

		donate_stuff = "\n".join(map(lambda key: f"• [{key}]({donate_links[key]})", donate_links))
		embed.description = "I host MangoByte on [DigitalOcean](https://www.digitalocean.com), which costs `$15` per month. "
		embed.description += "Mango makes 100,000+ api calls to opendota per month, which adds up to a bit over `$10` a month. (the [api calls start costing money](https://www.opendota.com/api-keys) if you do over 50,000 a month). "
		embed.description += "I have a job, and MangoByte won't be going down anytime soon, but if you want to help with the server costs, or just support me because you feel like it, feel free to donate using any of the links below. "
		embed.description += "I don't have any paid benefits/features at the moment for people who donate, but the support is definetly appreciated! "
		embed.description += f"\n\n{donate_stuff}"

		await ctx.send(embed=embed)


	@commands.command(aliases=[ "kitten", "cats", "kittens", "minnie", "minerva" ])
	async def cat(self, ctx):
		"""Gets a picture of my cat

		These are pictures of my (the developer of mangobyte) cat. Shes a bit over a year old now. Her name is Minnie. Short for Minerva. Also known as "Kitten", "Sneakerdoodle", or "Noodle." Shes a good kitten. """
		cat_dir = settings.resource("images/cat")
		imagepath = os.path.join(cat_dir, random.choice(os.listdir(cat_dir)))
		await ctx.send(file=discord.File(imagepath))

	@commands.command(aliases=[ "dogs", "doggos", "doggo", "comet", "fizzgig" ])
	async def dog(self, ctx):
		"""Gets a picture of one of my dogs

		These are pictures of my (the developer of mangobyte) dogs. Thier names are Fizzgig and Comet. One is floof. Other is big doggo. Floof older. Both good boys. """
		cat_dir = settings.resource("images/dog")
		imagepath = os.path.join(cat_dir, random.choice(os.listdir(cat_dir)))
		await ctx.send(file=discord.File(imagepath))



def setup(bot):
	bot.add_cog(General(bot))
