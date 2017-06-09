from .helpers import *
import os
import discord
from collections import OrderedDict


class BotDataItem:
	def __init__(self, botdata, list_key, primary_keys, defaults):
		self.__dict__.update({
			"_botdata": botdata,
			"_list_key": list_key,
			"_primary_keys": primary_keys,
			"defaults": defaults
		})

	@property
	def json_data(self):
		for item in self._botdata.json_data[self._list_key]:
			if all(item.get(key) == self._primary_keys[key] for key in self._primary_keys):
				return item
		return None

	def __getattr__(self, key):
		if key in self._primary_keys:
			return self._primary_keys[key]
		if key not in self.defaults:
			raise ValueError(f"Tried to get invalid '{key}' in {self._list_key}")
		if self.json_data:
			return self.json_data.get(key, self.defaults.get(key))
		return self.defaults.get(key)

	def __setattr__(self, key, val):
		if key in self._primary_keys:
			raise ValueError("You can't set a primary key")
		if key not in self.defaults:
			raise ValueError(f"Tried to set invalid '{key}' in {self._list_key}")

		# recreate to order correctly
		newdict = OrderedDict(self._primary_keys)
		for k in self.defaults:
			if k == key:
				if val != self.defaults[key]:
					newdict[k] = val
			elif self.json_data and k in self.json_data:
				newdict[k] = self.json_data[k]
		# now save to json
		if self.json_data:
			index = self._botdata.json_data[self._list_key].index(self.json_data)
			self._botdata.json_data[self._list_key][index] = newdict
		else:
			self._botdata.json_data[self._list_key].append(newdict)
		self._botdata.save_data()

class UserInfo(BotDataItem):
	def __init__(self, botdata, discord):
		BotDataItem.__init__(self, botdata, "userinfo", { "discord": discord }, OrderedDict([
			("steam32", None),
			("intro", ""),
			("outro", "")
		]))

	
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


