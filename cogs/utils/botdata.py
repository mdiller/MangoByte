from .helpers import *
import os
import discord
from collections import OrderedDict


class UserInfo:
	def __init__(self, botdata, userid):
		self.botdata = botdata
		self.discord = userid
		self.defaults = OrderedDict([
			("discord", self.discord),
			("steam32", None),
			("intro", ""),
			("outro", "")
		])

	def get_val(self, key):
		if self.json_data:
			return self.json_data.get(key, self.defaults.get(key))
		return self.defaults.get(key)

	def set_val(self, key, val):
		if not self.json_data:
			self.botdata.json_data['userinfo'].append(self.defaults)
		self.json_data[key] = val

	@property
	def json_data(self):
		for user in self.botdata.json_data['userinfo']:
			if user['discord'] == self.discord:
				return user
		# Should only happen when loading a userinfo for the first time
		return None

	@property
	def steam64(self):
		return self.steam32 + 76561197960265728

	@property
	def steam32(self):
		val = self.get_val("steam32")
		if (not val) and self.json_data:
			if self.json_data.get("steam64"):
				return self.json_data.get("steam64") - 76561197960265728
		return val


	@steam32.setter
	def steam32(self, value):
		self.set_val("steam32", value)
		
	@property
	def intro(self):
		return self.get_val("intro")

	@intro.setter
	def intro(self, value):
		self.set_val("intro", value)

	@property
	def outro(self):
		return self.get_val("outro")

	@outro.setter
	def outro(self, value):
		self.set_val("outro", value)

	
class GuildInfo:
	def __init__(self, botdata, guildid):
		self.botdata = botdata
		self.id = guildid
		if(self.json_data is None):
			self.botdata.json_data['guildinfo'].append(OrderedDict([
				("id", self.id),
				("voicechannel", None),
				("reactions", False),
				("invalidcommands", False),
				("banned_users", []),
				("ttschannel", [])
			]))
			self.botdata.save_data()

	@property
	def json_data(self):
		for guild in self.botdata.json_data['guildinfo']:
			if (guild['id'] == self.id):
				return guild
		# Should only happen when loading a guildinfo for the first time
		return None

	@property
	def voicechannel(self):
		return self.json_data.get("voicechannel", None)

	@voicechannel.setter
	def voicechannel(self, value):
		self.json_data["voicechannel"] = value
		self.botdata.save_data()

	@property
	def ttschannel(self):
		return self.json_data.get("ttschannel", None)

	@ttschannel.setter
	def ttschannel(self, value):
		self.json_data["ttschannel"] = value
		self.botdata.save_data()

	@property
	def reactions(self):
		return self.json_data.get("reactions", False)

	@property
	def invalidcommands(self):
		return self.json_data.get("invalidcommands", False)

	def is_banned(self, user):
		return user.id in self.json_data.get("banned_users", [])

	def botban(self, user):
		if self.json_data.get("banned_users") is None:
			self.json_data["banned_users"] = []
		if user.id not in self.json_data["banned_users"]:
			self.json_data["banned_users"].append(user.id)
			self.botdata.save_data()

	def botunban(self, user):
		if self.json_data.get("banned_users") is None:
			self.json_data["banned_users"] = []
		if user.id in self.json_data["banned_users"]:
			self.json_data["banned_users"].remove(user.id)
			self.botdata.save_data()



class BotData:
	def __init__(self):
		self.path = "botdata.json"
		self.defaults = OrderedDict([ ("userinfo" , []), ("guildinfo" , []) ])
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
		if isinstance(userid, discord.User):
			userid = userid.id
		return UserInfo(self, userid)

	def guildinfo(self, guildid):
		if isinstance(guildid, discord.Guild):
			guildid = guildid.id
		return GuildInfo(self, guildid)

	def guildinfo_list(self):
		guildinfos = []
		for data in self.json_data['guildinfo']:
			guildinfos.append(GuildInfo(self, data['id']))
		return guildinfos


