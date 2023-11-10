import asyncio
import datetime
import json
import os
import re
import subprocess
import sys
import typing
from collections import OrderedDict
import logging

import disnake
from disnake.ext import commands

logger = logging.getLogger("mangologger")

InterContext = typing.Union[disnake.Interaction, commands.Context]
ClipContext = typing.Union[disnake.Interaction, commands.Context, disnake.Guild]

MENTION_TRANSFORMS = {
	'@everyone': '@\u200beveryone',
	'@here': '@\u200bhere',
	r'<@!?[0-9]{17,22}>': '@deleted-user',
	r'<@&[0-9]{17,22}>': '@deleted-role'
}

MENTION_PATTERN = re.compile('|'.join(MENTION_TRANSFORMS.keys()))

audio_extensions = "mp3|wav|ogg"

async def safe_defer(inter: disnake.CmdInter):
	if inter.response._response_type is None:
		await inter.response.defer()

def slash_command_name(inter: disnake.CmdInter):
	result = inter.application_command.qualified_name
	if not isinstance(inter.application_command, commands.SubCommand):
		for option in inter.data.options:
			if option.type == disnake.OptionType.sub_command:
				result += " " + option.name
	return result

# expands a list of slash commands to include all sub commands
def slash_command_expand(list_of_commands: list[commands.InvokableSlashCommand]):
	new_list = []
	for command in list_of_commands:
		if isinstance(command, commands.InvokableSlashCommand):
			if command.children:
				for child in command.children.values():
					child.help_cog_name = command.cog_name
					new_list.append(child)
			else:
				command.help_cog_name = command.cog_name
				new_list.append(command)
	return new_list


def stringify_slash_command(inter: disnake.CmdInter):
	result = "/"
	result += slash_command_name(inter)
	if inter.filled_options:
		for key,value in inter.filled_options.items():
			if isinstance(value, disnake.User) or isinstance(value, disnake.Member):
				value = value.mention
			result += f" {key}: {value}"
	return result

def findfile(name, path):
	for root, dirs, files in os.walk(path):
		if name in files:
			return os.path.join(root, name)
	return None

def run_command(commandarray, returnerror=False):
	try:
		output = subprocess.check_output(commandarray).decode("utf-8")
		if returnerror:
			return (output, 0)
		else:
			return output
	except subprocess.CalledProcessError as e:
		if returnerror:
			return (e.output, e.returncode)
		else:
			raise

def get_time(timestr):
	negative = "-" in timestr
	timestr = timestr.replace("-", "")
	parts = timestr.split(":")
	result = None

	if len(parts) == 3:
		result = (int(parts[0]) * 3600) + (int(parts[1]) * 60) + float(parts[2])
	elif len(parts) == 2:
		result = (int(parts[0]) * 60) + float(parts[1])
	elif len(parts) == 1:
		result = float(parts[0])

	if result is not None:
		if negative:
			return 0 - result
		else:
			return result
	else:
		raise UserError(f"{timestr} is an invalid format for time. Time should be formatted as `minutes:seconds`.")

def get_pretty_time(s):
	seconds = s % 60
	minutes = ((s % 3600) - seconds) // 60
	hours = (s - (minutes * 60) - seconds) // 3600
	if hours:
		return f"{hours}:{minutes:0>2}:{seconds:0>2}"
	else:
		return f"{minutes}:{seconds:0>2}"

def capitalize_first(text):
	return text[0].upper() + text[1:]

def format_pascal_case(text):
	text = text.lower()
	words = text.split(" ")
	words = map(capitalize_first, words)
	return " ".join(words)


def format_duration_simple(duration):
	if duration >= 3600:
		return f"{int(duration / 3600)}:{int((duration / 60) % 60):02}:{duration % 60:02}"
	else:
		return f"{int((duration / 60) % 60)}:{duration % 60:02}"

# Gets mangobytes version from git commit number
def get_version():
	return run_command(["git", "rev-list", "--count", "master"])

def get_changelog():
	return run_command(["git", "log", "-n", "5", "--pretty=%H,%cd,%h,%s", "--date=unix"])

def write_json(filename, data):
	text = json.dumps(data, indent="\t")
	with open(filename, "w+") as f:
		f.write(text) # Do it like this so it doesnt break mid-file

def read_json(filename):
	with open(filename, encoding="utf-8") as f:
		return json.load(f, object_pairs_hook=OrderedDict)


class UserError(Exception):
	def __init__(self, message, embed=None, file=None):
		self.message = message
		self.embed = embed
		self.file = file
	async def send_self(self, ctx_inter: InterContext, botdata):
		kwargs = {}
		if self.embed:
			kwargs["embed"] = self.embed
		if self.file:
			kwargs["file"] = self.file

		await ctx_inter.send(self.message, **kwargs)


# thinks about messages
class Thinker():
	def __init__(self, bot):
		self.bot = bot
		self.messages = {} # Dictionary of message_id, { time: time, message: message }
		self.bot.loop.create_task(self.thinking_task())
		# May be used in future
		self.clocks = [ "🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚" ]

	async def think(self, message):
		self.messages[message.id] = {
			"message": message,
			"time": 0
		}
		await message.add_reaction("🤔")

	async def stop_thinking(self, message):
		last_time = self.messages.pop(message.id)
		await message.remove_reaction("🤔", self.bot.user)

	async def thinking_task(self):
		await self.bot.wait_until_ready()
		while not self.bot.is_closed:
			for message_id in self.messages:
				self.messages[message_id]["time"] += 1
			await asyncio.sleep(1)

class SimpleTimer():
	def __init__(self, message=None):
		self.message = message
		self.start = datetime.datetime.now()
		self.end = None
	
	def __enter__(self):
		self.start = datetime.datetime.now()
		return self

	def __exit__(self, type, value, traceback):
		self.stop()
		if self.message:
			print(self.message + f": {self.miliseconds} ms")

	def stop(self):
		self.end = datetime.datetime.now()

	@property
	def seconds(self):
		if self.end is None:
			self.stop()
		return int((self.end - self.start).total_seconds())
	
	@property
	def miliseconds(self):
		if self.end is None:
			self.stop()
		return int((self.end - self.start).total_seconds() * 1000.0)

	def __str__(self):
		s = self.seconds % 60
		m = self.seconds // 60
		text = f"{s} second{'s' if s != 1 else ''}"
		if m > 0:
			text = f"{m} minute{'s' if m != 1 else ''} and " + text
		return text

	def __repr__(self):
		return self.__str__()

class AsyncBundler():
	def __init__(self, tasks):
		# self.executor = task_executor
		self.tasks = tasks
		self.success_count = 0
		self.exceptions_dict = OrderedDict()
		self.completed = False

	async def exec_wrapper(self, task):
		try:
			result = await task
			self.success_count += 1
			return result
		except Exception as e:
			etype = str(type(e).__name__)
			logger.info(f"AsyncBundler found exception {etype}: {e}")
			if etype not in self.exceptions_dict:
				self.exceptions_dict[etype] = 0
			self.exceptions_dict[etype] += 1
			return None

	async def wait(self):
		tasks = list(map(lambda t: self.exec_wrapper(t), self.tasks))
		results = await asyncio.gather(*tasks)
		self.exceptions_dict = OrderedDict(sorted(self.exceptions_dict.items(), key=lambda t: t[0]))
		self.completed = True
		return results

	# gets the status as a string
	def status_as_string(self, success_str="succeeded"):
		result = f"{self.success_count} {success_str}"
		for e in self.exceptions_dict:
			result += f"\n{self.exceptions_dict[e]} failed with {e}"
		return result

class HttpError(UserError):
	"""An http error with an error code"""
	def __init__(self, message, url, code):
		super().__init__(message.format(code))
		self.code = code
		self.url = url


class Http404Error(HttpError):
	"""An http error with a 404 error code"""
	def __init__(self, message, url):
		super().__init__(message, url, 404)
	