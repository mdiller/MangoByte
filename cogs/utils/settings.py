from .helpers import *
import os
from collections import OrderedDict

#
# loosely based off of the red discord bot's settings
# to import from mangobyte.py, use:
# from __main__ import settings
#

class Settings:
	def __init__(self):
		self.path = "settings.json"
		self.defaults = OrderedDict([  ("token", ""), ("error_logging", False), ("debug", False) ])
		if not os.path.exists(self.path):
			self.json_data = self.defaults
			self.save_settings()
		else:
			current = read_json(self.path)
			if current.keys() != self.defaults.keys():
				for key in self.defaults.keys():
					if key not in current.keys():
						current[key] = self.defaults[key]
						print("Adding " + str(key) + " field to settings.json")
				write_json(self.path, current)
			self.json_data = read_json(self.path)
		if self.token == "":
			raise Exception("You need to put a bot 'token' in the settings.json file. See README.md for more information")

	def save_settings(self):
		write_json(self.path, self.json_data)

	# the token for your bot. see the README.md for more info on how to get one of these
	@property
	def token(self):
		return self.json_data["token"]

	# enables/disables logging of errors to discord text chat
	@property
	def error_logging(self):
		return self.json_data.get("error_logging", False)

	# enables/disables certain features like caching
	@property
	def debug(self):
		return self.json_data.get("debug", False)

	# an api key/secret for the reddit api (if not given, the ?reddit command wont work. see that command to see the format that the api key should be in)
	@property
	def reddit(self):
		return self.json_data.get("reddit", None)

	# an optional api key for the opendota api (if not given, you will be using the free tier of the opendota api which is good for up to 50,000 calls a month)
	@property
	def odota(self):
		return self.json_data.get("odota", None)

	@property
	def resourcedir(self):
		return "resource/" # self.json_data["resourcedir"]

	def resource(self, dir):
		return os.path.join(self.resourcedir, dir)

