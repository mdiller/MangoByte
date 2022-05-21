import os
from collections import OrderedDict

from utils.tools.helpers import *

#
# loosely based off of the red discord bot's settings
# to import from mangobyte.py, use:
# from utils.tools.globals import settings
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
						logger.info("Adding " + str(key) + " field to settings.json")
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

	# an api key/secret for the reddit api (if not given, the /reddit command wont work. see that command to see the format that the api key should be in)
	@property
	def reddit(self):
		return self.json_data.get("reddit", None)

	# an optional api key for the opendota api (if not given, you will be using the free tier of the opendota api which is good for up to 50,000 calls a month)
	@property
	def odota(self):
		return self.json_data.get("odota", None)

	# an optional api key for the stratz api (if not given, you won't be able to use the stratz api)
	@property
	def stratz(self):
		return self.json_data.get("stratz", None)

	# an optional api key for the topgg api. If not given, then the bot wont update the topgg api
	@property
	def topgg(self):
		return self.json_data.get("topgg", None)

	# an optional number of shards to use for the bot. by default will use as many as it thinks it needs
	@property
	def shard_count(self):
		return self.json_data.get("shard_count", None)

	# an optional path to a place to save server and member count information as json
	@property
	def infodump_path(self):
		return self.json_data.get("infodump_path", None)

	# an optional list of test-guilds for testing slash commands
	@property
	def test_guilds(self):
		return self.json_data.get("test_guilds", None)

	# logging information for how to log to a loki endpoint
	@property
	def loki(self):
		return self.json_data.get("loki", None)
	
	# used for storing emoji mango needs to use
	@property
	def emoji_dev_server(self):
		return self.json_data.get("emoji_dev_server", None)

	# BELOW ARE SOME STATICS NOT DEFINED IN THE SETTINGS.JSON FILE

	# permissions settings for the bot
	@property
	def permissions(self): # see https://discord.com/developers/applications/213476188037971968/oauth2/url-generator
		return 314432
	
	# the client_id of the bot
	@property
	def client_id(self):
		return 213476188037971968
	
	# an invite link for inviting the bot
	@property
	def invite_link(self): # see https://discord.com/developers/applications/213476188037971968/oauth2/url-generator
		return f"https://discordapp.com/oauth2/authorize?permissions={self.permissions}&scope=bot%20applications.commands&client_id={self.client_id}"

	# directory used for retrieving file resources for mango
	@property
	def resourcedir(self):
		return "resource/"


	def resource(self, dir):
		return os.path.join(self.resourcedir, dir)

settings = Settings()
