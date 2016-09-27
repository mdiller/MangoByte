import json
from collections import OrderedDict
# This module provides a simple way to interface with the settings.json file.
# it reads the file when the module loads and stores the variables in variables that are globally visible
#
# Example of what a settings.json file should look like:
# {
# 	"token": "<bot token goes here>",
# 	"resourcedir": "<resource directory goes here>",
# 	"dotavpk": "<extracted vpkdirectory goes here",
# 	"defaultvoice": "<ID of the default voice channel to connect to goes here>",
# 	"steamapikey": "<steam api key goes here>",
# 	"userinfo": [
# 		{
# 			"discord": "<discord id combination goes here>",
# 			"steam": "<steam id goes here>"
# 		}
# 	]
# }

class Settings:
	def __init__(self):
		with open('settings.json') as settings_file:
			data = json.load(settings_file, object_pairs_hook=OrderedDict)
		self.json_data = data
		self.token = data["token"]
		self.resourcedir = data["resourcedir"]
		self.dotavpk = data["dotavpk"]
		self.defaultvoice = data["defaultvoice"]
		self.steamapikey = data["steamapikey"]
		self.userinfo = []
		for user in data["userinfo"]:
			self.userinfo.append(UserInfo(user))

class UserInfo:
	def __init__(self, user_json):
		self.discord = user_json["discord"]
		self.steam = int(user_json["steam"])

# Adds a user to the settings.json file
# settings will need to be reloaded after this
def add_user(discord, steam, dota):
	with open('settings.json', 'w+') as settings_file:
		data = settings.json_data
		data["userinfo"].append(OrderedDict([
			("discord", discord),
			("steam", str(steam))
		]))
		json.dump(data, settings_file, indent=4)
	

settings = Settings()