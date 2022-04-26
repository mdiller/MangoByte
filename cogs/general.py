import datetime
import html
import json
import os
import random
import re
import string
from collections import OrderedDict
from io import BytesIO
import urllib.parse
import base64

import disnake
import praw
from bs4 import BeautifulSoup, Tag
from disnake.ext import commands, tasks
from utils.command import botdatatypes, checks
from utils.other import wikipedia
from utils.tools.botdata import UserInfo
from utils.tools.globals import (botdata, httpgetter, logger, settings)
from utils.tools.helpers import *
from utils.other.errorhandling import report_error

from cogs.audio import AudioPlayerNotFoundError
from cogs.dotabase import CURRENT_DOTA_PATCH_NUMBER
from cogs.mangocog import *


HELP_GUILD_LINK = "https://discord.gg/d6WWHxx"

DONATE_LINKS = {
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
	text = re.sub(r"<!--.*?-->\n?", "", text)
	text = "\n" + text
	result = {}
	pattern = re.compile(r"\n# ([^\n]+)\n([\s\S]*?)(?=\n# |$)")
	for match in pattern.finditer(text):
		name = match.group(1).strip()
		description = match.group(2).strip()
		description = re.sub("\n`", u"\n\u200b`", description)
		result[name] = description
	return result

def get_docs_keys():
	docs_data = load_md_as_dict(settings.resource("docs.md"))
	return list(docs_data.keys())

LOKI_APPLICATION_NAME = settings.loki["application"]
class BotStats():
	server_count: int
	user_count: int
	command_count: int
	top_commands: typing.List[str]
	def __init__(self, timeframe):
		self.timeframe = timeframe
		
	async def query_loki(self, query):
		baseurl = settings.loki["base_url"]
		url = f"{baseurl}/loki/api/v1/query"
		args = { "query": query }
		query_args = []
		for key,value in args.items():
			value = urllib.parse.quote(value.encode("utf-8"))
			query_args.append(f"{key}={value}")
		url += "?" + "&".join(query_args)

		userpass = f"{settings.loki['username']}:{settings.loki['password']}"
		headers = { "Authorization": f"Basic {base64.b64encode(userpass.encode()).decode()}" }

		data = await httpgetter.get(url, headers=headers)
		return data

	async def query_single_result(self, query):
		data = await self.query_loki(query)
		with open("temp.json", "w+") as f:
			f.write(json.dumps(data, indent="\t"))
		if len(data["data"]["result"]) == 0:
			return 0 # No results found, so default to 0
		return int(data["data"]["result"][0]["value"][1])
	
	async def query_user_count(self, timeframe):
		return await self.query_single_result(f'count(sum (count_over_time({{application="{LOKI_APPLICATION_NAME}", level="trace"}} | json | author_id != "" [{timeframe}])) by (author_id))')
	
	async def query_command_count(self, timeframe):
		return await self.query_single_result(f'sum(count_over_time({{application="{LOKI_APPLICATION_NAME}", level="trace"}} | json | type = "slash_command" or type = "prefix_command" [{timeframe}]))')

	async def query_top_commands(self, count, timeframe):
		data = await self.query_loki(f'topk({count}, sum(count_over_time({{application="{LOKI_APPLICATION_NAME}", level="trace"}} | json | type = "slash_command" [{timeframe}])) by (command))')
		cmds = []
		for item in data["data"]["result"]:
			cmds.append((item["metric"]["command"], int(item["value"][1])))
		cmds.sort(key=lambda c: c[1], reverse=True)
		return list(map(lambda c: c[0], cmds))

	async def update(self, bot: commands.Bot):
		self.server_count = len(bot.guilds)
		self.user_count = await self.query_user_count(self.timeframe)
		self.command_count = await self.query_command_count(self.timeframe)
		self.top_commands = await self.query_top_commands(5, self.timeframe)


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
		self.botstats_weekly = BotStats("7d")

	@commands.slash_command()
	async def misc(self, inter):
		"""A bunch of miscellaneous commands i made for fun"""
		pass # this is just a header for base commands
	
	@commands.slash_command()
	async def bot(self, inter):
		"""Gets information about mangobyte"""
		pass # this is just a header for base commands

	@commands.slash_command()
	async def userconfig(self, inter: disnake.CmdInter, setting: commands.option_enum(UserInfo.keys_list()), value: str):
		"""Configures the bot's user-specific settings

		Parameters
		----------
		setting: The setting you'd like to show/change
		value: The value you'd like to set for this setting, or 'show' to see the current value and more info"""
		if value == "show":
			value = None
		var = next((v for v in UserInfo.variables if v["key"] == setting), None)

		currentvalue = botdata.userinfo(inter.author)[var["key"]]
		if not value: # We are just getting a value
			await inter.send(embed=await botdatatypes.localize_embed(inter, var, currentvalue, f"/userconfig"))
		else: # We are setting a value
			value = await botdatatypes.parse(inter, var, value, currentvalue)
			botdata.userinfo(inter.author)[var["key"]] = value
			await inter.send(f"✅ {setting} has been set!")

	@commands.slash_command()
	async def ping(self, inter: disnake.CmdInter, count : commands.Range[1, 20] = 1):
		"""Pongs a number of times(within reason)"""
		ping_string = ""
		for i in range(0, count):
			ping_string += "pong "
		await inter.send(ping_string)

	@commands.slash_command()
	async def echo(self, inter: disnake.CmdInter, message: str):
		"""Echos the given message
		
		Parameters
		----------
		message: The message to echo
		"""
		await inter.send(message)
		

	@bot.sub_command(name="changelog")
	async def changelog(self, inter: disnake.CmdInter):
		"""Gets a rough changelog for mangobyte"""
		await inter.response.defer()
		commit_url = "https://github.com/mdiller/MangoByte"
		description = f"For more information check out the [commit history]({commit_url}/commits/master) on GitHub, or visit the [Mangobyte Info Server]({HELP_GUILD_LINK}), and subscribe/follow the #updates channel.\n"
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

		embed = disnake.Embed(description=description, color=disnake.Color.green())

		if recent_date != 0:
			embed.timestamp = datetime.datetime.fromtimestamp(recent_date, tz=datetime.timezone.utc)
			embed.set_footer(text="Most recent change at")

		embed.set_author(name="Changelog", url=f"{commit_url}/commits/master")
		await inter.send(embed=embed)

	@bot.sub_command(name="info")
	async def info(self, inter: disnake.CmdInter):
		"""Prints info about mangobyte"""
		github = "https://github.com/mdiller/MangoByte"
		python_version = "[Python {}.{}.{}]({})".format(*os.sys.version_info[:3], "https://www.python.org/")
		library_url = "https://github.com/DisnakeDev/disnake"

		embed = disnake.Embed(description="A bot for playing audio clips and Dota 2 related commands", color=disnake.Color.green())

		embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url, url=github)

		embed.add_field(name="Development Info", value=(
			"Developed as an open source project, hosted on [GitHub]({}). "
			"Implemented using {} and a python discord api wrapper called [disnake]({})".format(github, python_version, library_url)))

		embed.add_field(name="Help", value=(
			f"If you want to invite mangobyte to your server/guild, click this [invite link]({settings.invite_link}). "
			f"If you have a question or suggestion, check out the [Help Server/Guild]({HELP_GUILD_LINK})."))

		cmdpfx = botdata.command_prefix_guild(inter.guild)
		embed.add_field(name="Find Out More", value=(
			f"• Browse commands and command categories via the `{cmdpfx}help` command\n"
			f"• Learn more about mangobyte's core features with the `/docs` command\n"
			f"• Per-user configuration is available via `/userconfig`\n"
			f"• Configure settings for your server via `/config`"), inline=False)

		owner = (await self.bot.application_info()).owner

		embed.set_footer(text="MangoByte developed by {}".format(owner.name), icon_url=owner.avatar.url)

		await inter.send(embed=embed)

	@bot.sub_command(name="invite")
	async def invite(self, inter: disnake.CmdInter):
		"""Shows the invite link"""
		await inter.send(settings.invite_link)

	@bot.sub_command(name="stats")
	async def stats(self, inter: disnake.CmdInter):
		"""Displays some bot statistics"""
		await inter.response.defer()

		if not settings.loki:
			await inter.send("Stats not available for this bot. Whoever's running it hasnt set up loki")
			return

		embed = disnake.Embed(color=disnake.Color.green())
		embed.description = "Note: The data for these stats began on March 22nd."

		embed.set_author(name=self.bot.user.name + " Stats (Last 7 Days)", icon_url=self.bot.user.avatar.url)

		botstats = self.botstats_weekly
		embed.add_field(name="Servers/Guilds", value=f"{botstats.server_count:,}")
		embed.add_field(name="Unique Users", value=f"{botstats.user_count:,}")
		embed.add_field(name="Total Commands", value=f"{botstats.command_count:,}")
		embed.add_field(name="Top Commands", value="\n".join(map(lambda c: f"`/{c}`", botstats.top_commands)))
		
		embed.set_footer(text="stats refreshes every hour")

		await inter.send(embed=embed)

	@misc.sub_command(name="lasagna")
	async def misc_lasagna(self, inter: disnake.CmdInter):
		"""Posts an image of a baked italian dish"""
		lasagna_images = [
			"images/lasagna1.jpg",
			"images/lasagna2.jpg",
			"images/lasagna3.jpg",
			"images/lasagna4.jpg",
			"images/lasagna5.jpg",
			"images/lasagna6.jpg",
			"images/lasagna7.jpg",
			"images/lasagna8.jpg",
			"images/lasagna9.jpg",
		]
		await inter.send(file=disnake.File(settings.resource(random.choice(lasagna_images))))

	@misc.sub_command(name="scramble")
	async def misc_scramble(self, inter: disnake.CmdInter, message: str):
		"""Scrambles the insides of words
		
		Parameters
		----------
		message: The message to scramble
		"""

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

		await inter.send(" ".join(results))

	@commands.slash_command()
	async def wiki(self, inter: disnake.CmdInter, thing: str):
		"""Looks up a thing on wikipedia
		
		Parameters
		----------
		thing: The thing to look up on wikipedia
		"""
		await inter.response.defer()

		page = await wikipedia.get_wikipedia_page(thing)

		embed = disnake.Embed(description=page.markdown)
		embed.title = f"**{page.title}**"
		embed.url = page.url

		footer_text = "Retrieved from Wikipedia"

		if page.image:
			if (not isinstance(inter.channel, disnake.DMChannel)) and inter.channel.is_nsfw():
				embed.set_image(url=page.image)
			else:
				footer_text += ". (Image omitted because I can't check if it is NSFW) D:"

		embed.set_footer(text=footer_text, icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Wikipedia's_W.svg/2000px-Wikipedia's_W.svg.png")
		
		await inter.send(embed=embed)

	@commands.slash_command()
	async def reddit(self, inter: disnake.CmdInter, post: str):
		"""Displays a formatted reddit post

		Parameters
		----------
		post: The url or id of the post to link"""
		if settings.reddit is None:
			raise UserError("This MangoByte has not been configured to get reddit submissions. Gotta add your info to `settings.json`")

		await inter.response.defer()

		reddit = praw.Reddit(client_id=settings.reddit["client_id"],
			client_secret=settings.reddit["client_secret"],
			user_agent=settings.reddit["user_agent"])

		try:
			if re.search(r"(redd\.it|reddit.com)", post):
				if not re.search(r"https?://", post):
					post = "http://" + post
				submission = reddit.submission(url=post)
			else:
				submission = reddit.submission(id=post)
			description = submission.selftext
		except:
			raise UserError("Couldn't properly find that reddit submission")

		
		if submission.over_18:
			if (isinstance(inter.channel, disnake.DMChannel)) or (not inter.channel.is_nsfw()):
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

		embed = disnake.Embed(description=description, color=disnake.Color(int("ff4500", 16)))
		embed.set_footer(text=f"/r/{submission.subreddit}", icon_url="https://images-na.ssl-images-amazon.com/images/I/418PuxYS63L.png")

		embed.title = submission.title
		embed.url = submission.shortlink

		url_ext = submission.url.split(".")[-1]

		if url_ext in ["gifv", "gif", "png", "jpg", "jpeg"]:
			image_url = submission.url
			if url_ext == "gifv":
				image_url = image_url.replace(".gifv", ".gif")
			embed.set_image(url=image_url)

		await inter.send(embed=embed)

	@misc.sub_command(name="showerthought")
	async def misc_showerthought(self, inter: disnake.CmdInter):
		"""Gets a top post from the r/ShowerThoughts subreddit"""
		await inter.response.defer()

		thought = random.choice(self.showerthoughts_data)

		author = thought["author"]
		author = f"u/{author}" if author else "[deleted]"

		embed = disnake.Embed()

		embed.description = thought["title"]
		embed.timestamp = datetime.datetime.fromtimestamp(thought["timestamp"], tz=datetime.timezone.utc)
		embed.set_footer(text=author)

		await inter.send(embed=embed)

	@misc.sub_command(name="ask")
	async def misc_ask(self, inter: disnake.CmdInter, question : str=""):
		"""A magic 8-ball style question answerer

		Parameters
		----------
		question: The question you want answered"""
		random.seed(question)
		for check in self.questions:
			if re.search(check["regex"], question):
				clip = await self.get_clip(random.choice(check['responses']), inter)
				await inter.send(clip.text)
				try:
					await self.play_clip(clip, inter)
				except AudioPlayerNotFoundError:
					pass # Not needed for this 
				return

	@commands.user_command(name="insult")
	async def insult_user(self, inter: disnake.CmdInter, victim: disnake.User=None):
		"""Insults the victim"""
		await self._insult_impl(inter, victim)

	@misc.sub_command(name="insult")
	async def insult_slash(self, inter: disnake.CmdInter, victim: disnake.User=None):
		"""Insults the given victim, or you if you dont target anyone

		Parameters
		----------
		victim: The target of your insult"""
		await self._insult_impl(inter, victim)

	async def _insult_impl(self, inter: disnake.CmdInter, victim: disnake.User=None):
		if victim is None:
			victim = inter.author

		start = "You "
		start_local = start

		template = "{animal|food|furniture|instrument:NOSPACE}-{body_part_ed} {relation} of a {animal|furniture}"

		if victim.id == self.bot.user.id:
			template = "lovely fellow"
		start = f"{victim.mention}, you're a "
		start_local = f"{victim.name}, you're a "

		result = fill_word_template(template, self.words)

		await inter.send(start + result)
		if inter.guild and inter.guild.me.voice:
			await self.play_clip(f"tts:{start_local}{result}", inter)
	
	@misc.sub_command(name="random")
	async def misc_random(self, inter: disnake.CmdInter, maximum: int, minimum: int = 0):
		"""Gets a random number between the minimum and maximum (inclusive)

		Parameters
		----------
		maximum: The highest number the return value can be
		minimum: The lowest number the return value can be"""
		result = None
		if maximum < minimum:
			result = random.randint(maximum, minimum)
		else:
			result = random.randint(minimum, maximum)
		await inter.send(result)
	
	@misc.sub_command(name="choose")
	async def misc_choose(self, inter: disnake.CmdInter, options: str):
		"""Randomly chooses one of the given options

		Parameters
		----------
		options: A space-separated list of options to choose from"""
		options = options.split(" ")
		await inter.send(random.choice(options))

	@commands.slash_command()
	async def docs(self, inter: disnake.CommandInteraction, topic: str = commands.Param(choices=get_docs_keys())):
		"""Shows some documentation about a specific part of the bot

		Parameters
		----------
		topic: The topic to get documentation for
		"""
		found_topic = topic

		embed = disnake.Embed()
		embed.title = found_topic
		embed.description = self.docs_data[found_topic]
		await inter.send(embed=embed)
	
	@tasks.loop(hours=1)
	async def update_botstats(self):
		logger.info("task_triggered: update_botstats()")
		try:
			await self.botstats_weekly.update(self.bot)
		except Exception as e:
			await report_error("update_botstats()", e)

	@tasks.loop(hours=12)
	async def update_topgg(self):
		logger.info("task_triggered: update_topgg()")
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
		except Exception as e: # HttpError
			await report_error("update_topgg()", e)

	@tasks.loop(hours=12)
	async def do_infodump(self):
		logger.info("task_triggered: do_infodump()")
		if not settings.infodump_path:
			return # nothing to do here

		try:
			guilds_count = len(self.bot.guilds)
			member_count = botdata.count_users_with_key("steam")

			data = {
				"servers": guilds_count,
				"registered_users": member_count
			}
			with open(settings.infodump_path, "w+") as f:
				f.write(json.dumps(data))
		except Exception as e:
			await report_error("do_infodump()", e)
		logger.event("infodump", data)

	@tasks.loop(minutes=5)
	async def check_dota_patch(self):
		logger.info("task_triggered: check_dota_patch()")
		url = "https://www.dota2.com/patches/"
		try:
			text = await httpgetter.get(url, return_type="text")
		except HttpError as e:
			logger.info(f"patches update failed with http {e.code} error")
			await self.send_owner(f"patches update failed the check with a http {e.code} error")
			return # failed, so return
		except Exception as e:
			etype = str(type(e).__name__)
			logger.info(f"patches update failed the check w/ exception {etype}: {e}")
			await self.send_owner(f"patches update failed the check w/ exception {etype}: {e}")
			return # failed, so return
		soup = BeautifulSoup(text, "html.parser")

		logger.info("patch parse starting")

		current_patch = soup.find(name="title").contents[0]
		old_patch = botdata["dotapatch"]

		if old_patch == current_patch:
			return # thats the current patch, do nothing
		if current_patch.strip() == "Gameplay Update":
			return # thats what happens when theyre tryna switch it and theyre in the process, so give it a minute and try again later
		logger.info(f"\"{current_patch}\"")
		logger.info(current_patch == "Gameplay Update")
		logger.info(str(current_patch) == "Gameplay Update")
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
		embed = disnake.Embed(timestamp=datetime.datetime.utcnow())
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
					logger.info(f"couldn't find channel {guildinfo.dotapatchchannel} when announcing dota patches")

		userinfos = botdata.userinfo_list()
		for userinfo in userinfos:
			if userinfo.dmdotapatch:
				user = self.bot.get_user(userinfo.discord)
				if user is not None:
					messageables.append(user)
				else:
					logger.info(f"couldn't find user {userinfo.discord} when announcing dota patches")

		tasks = []
		for messageable in messageables:
			tasks.append(messageable.send(embed=embed))

		bundler = AsyncBundler(tasks)
		logger.info("waiting for dota patch bundle to complete")
		await bundler.wait()
		logger.info("dota patch bundle completed")
		await self.send_owner("__Dota Patch Sent!__\n" + bundler.status_as_string())


	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author == self.bot.user:
			return # ignore stuff from myself

		if message.guild is None:
			return # only keep going if we're in a guild
		guildinfo = botdata.guildinfo(message.guild.id)

		if message.author.bot and (message.author.id in guildinfo.allowedbots) or (message.webhook_id and guildinfo.allowwebhooks):
			# execute this command from a bot because we're allowing it
			ctx = await self.bot.get_context(message)
			await self.bot.invoke(ctx)

		if message.content.startswith(self.cmdpfx(message.guild)):
			return # ignore stuff that starts with the command prefix

		if not guildinfo.reactions:
			return # only keep going for guilds with reactions enabled

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
	async def on_command(self, ctx: commands.Context):
		logger.event("prefix_command", {
			"command": ctx.command.name,
			"message_id": ctx.message.id,
			"author_id": ctx.message.author.id,
			"server_id": ctx.message.guild.id if ctx.guild else None,
			"channel_id": ctx.message.channel.id,
			"timestamp": ctx.message.created_at.isoformat(),
			"content": ctx.message.content,
			"clean_content": ctx.message.clean_content
		})

	@commands.Cog.listener()
	async def on_slash_command(self, inter: disnake.CommandInteraction):
		logger.event("slash_command", {
			"command": slash_command_name(inter),
			"inter_id": inter.id,
			"author_id": inter.author.id,
			"server_id": inter.guild.id if inter.guild else None,
			"channel_id": inter.channel.id,
			"timestamp": inter.created_at.isoformat(),
			"content": stringify_slash_command(inter)
		})
		
	@commands.Cog.listener()
	async def on_user_command(self, inter: disnake.CmdInter):
		logger.event("user_command", {
			"command": inter.application_command.qualified_name,
			"inter_id": inter.id,
			"author_id": inter.author.id,
			"server_id": inter.guild.id if inter.guild else None,
			"channel_id": inter.channel.id,
			"timestamp": inter.created_at.isoformat(),
			"content": "@" + inter.application_command.qualified_name + " " + inter.target.mention
		})

	@commands.Cog.listener()
	async def on_command_completion(self, ctx: commands.Context):
		logger.event("command_finished", {
			"message_id": ctx.message.id
		})
	
	@commands.Cog.listener()
	async def on_slash_command_completion(self, inter: disnake.CmdInter):
		logger.event("command_finished", {
			"inter_id": inter.id
		})
	
	@commands.Cog.listener()
	async def on_user_command_completion(self, inter: disnake.CmdInter):
		logger.event("command_finished", {
			"inter_id": inter.id
		})

	@bot.sub_command(name="donate")
	async def donate(self, inter: disnake.CmdInter):
		"""Posts some links with info about how to donate to the developer"""
		embed = disnake.Embed()

		donate_stuff = "\n".join(map(lambda key: f"• [{key}]({DONATE_LINKS[key]})", DONATE_LINKS))
		embed.description = "I host MangoByte on [DigitalOcean](https://www.digitalocean.com), which costs ~`$15` per month. "
		embed.description += "Mango makes 100,000+ api calls to opendota per month, which adds up to a bit over `$10` a month. (the [api calls start costing money](https://www.opendota.com/api-keys) if you do over 50,000 a month). "
		embed.description += "I have a job, and MangoByte won't be going down anytime soon, but if you want to help with the server costs, or just support me because you feel like it, feel free to donate using any of the links below. "
		embed.description += "I don't have any paid benefits/features at the moment for people who donate, but the support is definetly appreciated! "
		embed.description += f"\n\n{donate_stuff}"

		await inter.send(embed=embed)

	@misc.sub_command(name="cat")
	async def misc_cat(self, inter: disnake.CmdInter):
		"""Gets a picture of the developer's cat"""
		cat_dir = settings.resource("images/cat")
		imagepath = os.path.join(cat_dir, random.choice(os.listdir(cat_dir)))
		await inter.send(file=disnake.File(imagepath))

	@misc.sub_command(name="dog")
	async def misc_dog(self, inter: disnake.CmdInter):
		"""Gets a picture of one of the developer's dogs"""
		dog_dir = settings.resource("images/dog")
		imagepath = os.path.join(dog_dir, random.choice(os.listdir(dog_dir)))
		await inter.send(file=disnake.File(imagepath))



def setup(bot):
	bot.add_cog(General(bot))
