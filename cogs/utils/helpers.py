import os
import sys
import json
import subprocess
import asyncio
from collections import OrderedDict

audio_extensions = "mp3|wav|ogg"

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
	with open(filename) as f:
		return json.load(f, object_pairs_hook=OrderedDict)


class UserError(Exception):
	def __init__(self, message, embed=None, file=None):
		self.message = message
		self.embed = embed
		self.file = file
	async def send_self(self, ctx):
		kwargs = {}
		if self.embed:
			kwargs["embed"] = self.embed
		if self.file:
			kwargs["file"] = self.file
		await ctx.send(self.message, **kwargs)


# thinks about messages
class Thinker():
	def __init__(self, bot):
		self.bot = bot
		self.messages = {} # Dictionary of message, time
		self.bot.loop.create_task(self.thinking_task())
		# May be used in future
		self.clocks = [ "🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚" ]

	async def think(self, message):
		self.messages[message] = 0
		await message.add_reaction("🤔")

	async def stop_thinking(self, message):
		last_time = self.messages.pop(message)
		await message.remove_reaction("🤔", self.bot.user)

	async def thinking_task(self):
		await self.bot.wait_until_ready()
		while not self.bot.is_closed:
			for message in self.messages:
				self.messages[message] += 1
			await asyncio.sleep(1)


class HttpError(UserError):
	"""An http error with an error code"""
	def __init__(self, message, code):
		super().__init__(message.format(code))
		self.code = code


class Http404Error(HttpError):
	"""An http error with a 404 error code"""
	def __init__(self, message):
		super().__init__(message, 404)
	