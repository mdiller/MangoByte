from .helpers import *
import os
import discord
from collections import OrderedDict

class ListVar:
	def __init__(self, t):
		self.type = t

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

	__getitem__ = __getattr__
	__setitem__ = __setattr__

	# adds an item to a list variable, like banned_users
	def add_list_item(self, key, item):
		if item not in self[key]:
			new_list = list(self[key])
			new_list.append(item)
			self[key] = new_list

	# removes an item from a list variable, like banned_users
	def remove_list_item(self, key, item):
		if item in self[key]:
			new_list = list(self[key])
			new_list.remove(item)
			self[key] = new_list

class UserInfo(BotDataItem):
	def __init__(self, botdata, discord):
		BotDataItem.__init__(self, botdata, "userinfo", { "discord": discord }, OrderedDict([
			("steam32", None),
			("intro", ""),
			("outro", "")
		]))
	
class GuildInfo(BotDataItem):
	def __init__(self, botdata, guildid):
		defaults = OrderedDict([ 
			("voicechannel", None),
			("invalidcommands", False),
			("banned_users", [])
		])
		for var in self.variables:
			defaults[var["key"]] = var["default"]
		BotDataItem.__init__(self, botdata, "guildinfo", { "id": guildid }, defaults)

	variables = [
		{
			"key": "reactions",
			"default": False,
			"type": bool,
			"description": "Allows mangobyte to react to users messages depending on what they are saying",
			"example": "enable"
		},
		{
			"key": "ttschannel",
			"default": None,
			"type": discord.TextChannel,
			"description": "If someone types in the given channel, mangobyte will automatically interpret it as a `?smarttts` command, and say it in the voicechannel that they are in",
			"example": "#tts"
		},
		{
			"key": "botadmin",
			"default": None,
			"type": discord.Role,
			"description": "Users who have the specified role will be able to use commands from the admin section. To set this role, do `?config botadmin <role>` where <role> is an @mention of a role in the server",
			"example": "@BotAdmin"
		},
		{
			"key": "intros",
			"default": True,
			"type": bool,
			"description": "Allows mangobyte to announce users when they enter the voice channel that mangobyte is currently in",
			"example": "disable"
		},
		{
			"key": "outros",
			"default": True,
			"type": bool,
			"description": "Allows mangobyte to announce when users leave the voice channel that mangobyte is currently in",
			"example": "disable"
		},
		{
			"key": "ttslang",
			"default": "en-au",
			"type": "GttsLang",
			"description": "Sets the language/voice that mangobyte will use to speak using the `?tts` command. To see a list of all of the possible languages, check out [this file](https://github.com/mdiller/MangoByte/blob/master/resource/json/gtts_languages.json) in the github repo",
			"example": "Russian"
		}
	]

	def is_banned(self, user):
		return user.id in self.banned_users

	def botban(self, user):
		self.add_list_item("banned_users", user.id)

	def botunban(self, user):
		self.remove_list_item("banned_users", user.id)



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

	def userinfo_list(self):
		userinfos = []
		for data in self.json_data['userinfo']:
			userinfos.append(UserInfo(self, data["discord"]))
		return userinfos


