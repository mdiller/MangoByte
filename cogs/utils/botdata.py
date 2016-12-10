from .helpers import *
import os
from collections import OrderedDict


class UserInfo:
	def __init__(self, botdata, userid):
		self.botdata = botdata
		self.discord = userid
		if(self.json_data is None):
			self.botdata.json_data['userinfo'].append(OrderedDict([
				("discord", self.discord),
				("steam64", None),
				("intro", ""),
				("outro", "")
			]))
			self.botdata.save_data()

	@property
	def json_data(self):
		for user in self.botdata.json_data['userinfo']:
			if (user['discord'] == self.discord):
				return user
		# Should only happen when loading a userinfo for the first time
		return None

	@property
	def steam64(self):
		return self.json_data.get("steam64", None)

	@steam64.setter
	def steam64(self, value):
		self.json_data["steam64"] = value
		self.botdata.save_data()

	@property
	def steam32(self):
		return self.steam64 - 76561197960265728
		
	@property
	def intro(self):
		return self.json_data.get("intro", "")

	@intro.setter
	def intro(self, value):
		self.json_data["intro"] = value
		self.botdata.save_data()

	@property
	def outro(self):
		return self.json_data.get("outro", "")

	@outro.setter
	def outro(self, value):
		self.json_data["outro"] = value
		self.botdata.save_data()

	

class BotData:
	def __init__(self):
		self.path = "botdata.json"
		self.defaults = OrderedDict([ ("userinfo" , []) ])
		if not os.path.exists(self.path):
			self.json_data = self.defaults
			self.save_data()
		else:
			current = read_json(self.path)
			if current.keys() != self.defaults.keys():
				for key in self.defaults.keys():
					if key not in current.keys():
						current[key] = self.defaults[key]
						print("Adding " + str(key) + " field to botdata.json")
				write_json(self.path, current)
			self.json_data = read_json(self.path)

	def save_data(self):
		write_json(self.path, self.json_data)

	def userinfo(self, userid):
		return UserInfo(self, userid)

