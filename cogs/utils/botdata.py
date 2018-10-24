from .helpers import *
import os
import discord
import cogs.utils.botdatatypes as types
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
		defaults = OrderedDict([])
		for var in self.variables:
			defaults[var["key"]] = var["default"]
		BotDataItem.__init__(self, botdata, "userinfo", { "discord": discord }, defaults)

	variables = [
		{
			"key": "steam",
			"default": None,
			"type": types.SteamId,
			"description": "This links your steam account to your discord account for mangobyte. You have to give this either your steam32 or steam64 id. An easy way to find this is to open dota and find your 'Friend ID', or look at the end of your dotabuff/opendota profile url.\n\nIf you open up dota and go to your profile, your 'Friend ID' will be just under your name, and will look like this:\n<:steam:414724031380586496> **FRIEND ID:** `<number>`\n\nIn which case you should do `?userconfig steam <number>`\n\nTo un-register, try setting this to `clear` or `reset`",
			"example": "70388657"
		},
		{
			"key": "intro",
			"default": "local:helloits",
			"type": types.ShortClip,
			"description": "This sets the clip that will play whenever you join a voice channel that mangobyte is in. Note that this clip cannot be longer than 4.5 seconds\n\nTo make it so no clip plays when you join the channel, try setting this to `none`, `silent`, `off`, or `disable`",
			"example": "local:math"
		},
		{
			"key": "outro",
			"default": "local:farewell",
			"type": types.ShortClip,
			"description": "This sets the clip that will play whenever you leave a voice channel that mangobyte is in. Note that this clip cannot be longer than 4.5 seconds\n\nTo make it so no clip plays when you join the channel, try setting this to `none`, `silent`, `off`, or `disable`",
			"example": "dota:troll_warlord_troll_lose_03"
		},
		{
			"key": "introtts",
			"default": "it's",
			"type": types.ShortText,
			"description": "This is what is said before saying your name when announcing that you have joined the channel. To set your tts to be nothing, try setting this to `nothing` or `none`\n\nNote that this clip can be no longer than 32 characters.",
			"example": "it's the magnificent"
		},
		{
			"key": "outrotts",
			"default": "has left!",
			"type": types.ShortText,
			"description": "This is what is said after saying your name when announcing that you have left the channel. To set your tts to be nothing, try setting this to `nothing` or `none`\n\nNote that this clip can be no longer than 32 characters.",
			"example": "dun gone left"
		}
	]
	
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
			"key": "prefix",
			"default": "?",
			"type": types.CommandPrefix,
			"description": "Configures the character to use to prefix your commands for this server",
			"example": "!"
		},
		{
			"key": "reactions",
			"default": False,
			"type": types.Boolean,
			"description": "Allows mangobyte to react to users messages depending on what they are saying",
			"example": "enable"
		},
		{
			"key": "ttschannel",
			"default": None,
			"type": types.TextChannel,
			"description": "If someone types in the given channel, mangobyte will automatically interpret it as a `?smarttts` command, and say it in the voicechannel that they are in. To say something in this channel without doing a tts, try adding a `//` or `#` to the front of your message",
			"example": "#tts"
		},
		{
			"key": "botadmin",
			"default": None,
			"type": types.Role,
			"description": "Users who have the specified role will be able to use commands from the admin section. To set this role, do `?config botadmin <role>` where <role> is an @mention of a role in the server",
			"example": "@BotAdmin"
		},
		{
			"key": "intros",
			"default": True,
			"type": types.Boolean,
			"description": "Allows mangobyte to announce users when they enter the voice channel that mangobyte is currently in",
			"example": "disable"
		},
		{
			"key": "outros",
			"default": True,
			"type": types.Boolean,
			"description": "Allows mangobyte to announce when users leave the voice channel that mangobyte is currently in",
			"example": "disable"
		},
		{
			"key": "ttslang",
			"default": "en-au",
			"type": types.GttsLang,
			"description": "Sets the language/voice that mangobyte will use to speak using the `?tts` command. To see a list of all of the possible languages, check out [this file](https://github.com/mdiller/MangoByte/blob/master/resource/json/gtts_languages.json) in the github repo",
			"example": "Russian"
		},
		{
			"key": "usenickname",
			"default": False,
			"type": types.Boolean,
			"description": "Sets whether mangobyte will use the user's name or nickname when announcing that they have joined or left a channel",
			"example": "enable"
		},
		{
			"key": "announcetts",
			"default": False,
			"type": types.Boolean,
			"description": "Sets whether mangobyte announce the user's name before playing the clip when they the user plays a clip by typing something in the tts channel",
			"example": "enable"
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
		if isinstance(userid, discord.User) or  isinstance(userid, discord.Member):
			userid = userid.id
		return UserInfo(self, userid)

	def guildinfo(self, guildid):
		if isinstance(guildid, discord.ext.commands.Context):
			guildid = guildid.message.guild
		if isinstance(guildid, discord.abc.GuildChannel):
			guildid = guildid.guild
		if isinstance(guildid, discord.Guild):
			guildid = guildid.id
		if guildid is None:
			return None
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


	# gets the command prefix
	def command_prefix(self, ctx):
		return self.command_prefix_guild(ctx) # will act the same for self.guildinfo

	def command_prefix_botmessage(self, bot, message):
		return self.command_prefix_guild(message.guild)

	def command_prefix_guild(self, guild):
		guildinfo = self.guildinfo(guild)
		if guildinfo is not None:
			return guildinfo.prefix
		else:
			return "?"

		
