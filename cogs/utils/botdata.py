from .helpers import *
import os
import discord
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
		if self.steam64 is None:
			return None
		return self.steam64 - 76561197960265728

	@steam32.setter
	def steam32(self, value):
		self.steam64 = value + 76561197960265728
		
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

	
class ServerInfo:
	def __init__(self, botdata, serverid):
		self.botdata = botdata
		self.id = serverid
		if(self.json_data is None):
			self.botdata.json_data['serverinfo'].append(OrderedDict([
				("id", self.id),
				("voicechannel", None),
				("reactions", False),
				("invalidcommands", False),
				("banned_users", [])
			]))
			self.botdata.save_data()

	@property
	def json_data(self):
		for server in self.botdata.json_data['serverinfo']:
			if (server['id'] == self.id):
				return server
		# Should only happen when loading a serverinfo for the first time
		return None

	@property
	def voicechannel(self):
		return self.json_data.get("voicechannel", None)

	@voicechannel.setter
	def voicechannel(self, value):
		self.json_data["voicechannel"] = value
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
		self.defaults = OrderedDict([ ("userinfo" , []), ("serverinfo" , []) ])
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

	def serverinfo(self, serverid):
		if isinstance(serverid, discord.Server):
			serverid = serverid.id
		return ServerInfo(self, serverid)

	def serverinfo_list(self):
		serverinfos = []
		for data in self.json_data['serverinfo']:
			serverinfos.append(ServerInfo(self, data['id']))
		return serverinfos


