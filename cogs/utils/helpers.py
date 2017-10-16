import os
import sys
import json
import subprocess
import asyncio
from collections import OrderedDict

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


def get_pretty_time(s):
	seconds = s % 60
	minutes = ((s % 3600) - seconds) // 60
	hours = (s - (minutes * 60) - seconds) // 3600
	if hours:
		return f"{hours}:{minutes:0>2}:{seconds:0>2}"
	else:
		return f"{minutes}:{seconds:0>2}"

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
	def __init__(self, message):
		self.message = message

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
	