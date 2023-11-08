import re
from abc import abstractmethod

import disnake
from disnake.ext import commands
from utils.tools.helpers import *
from utils.tools.settings import settings


class InvalidInputError(UserError):
	def __init__(self, message):
		super().__init__(f"Invalid Input. {message}")


async def localize_embed(inter: disnake.Interaction, var, value, example_command):
	embed = disnake.Embed(description=var["description"])
	embed.set_author(name=var["key"])

	if not issubclass(var["type"], ConfigVarType):
		raise ValueError(f"Bad variable type for {example_command} variable {var['key']}")

	if var.get("list"):
		localized_value = ""
		for v in value:
			localized_value += await var["type"].localize(v, inter) + "\n"
		if localized_value == "":
			localized_value = "None"
	else:
		localized_value = await var["type"].localize(value, inter)

	embed.add_field(name="Current Value", value=localized_value)
	embed.add_field(name="Example", value=f"`{example_command} {var['key']} {var['example']}`")
	return embed


async def parse(inter, var, value, currentvalue):
	if value in [ "default", "reset", "clear", "null" ]:
		return var["default"]

	if var.get("list"):
		currentvalue = currentvalue.copy()
		subcommands = [ "add", "remove" ]
		if " " in value:
			subcommand, value = value.split(" ", 1)
		else:
			subcommand = None

		if subcommand == "add":
			value = await var["type"].parse(value, inter)
			if value in currentvalue:
				raise InvalidInputError("That's already been added!")
			currentvalue.append(value)
			return currentvalue
		elif subcommand == "remove":
			value = await var["type"].parse(value, inter)
			if value not in currentvalue:
				raise InvalidInputError("That's not currently in there.")
			currentvalue.remove(value)
			return currentvalue
		else:
			raise InvalidInputError("Start with 'add' or 'remove'")


	return await var["type"].parse(value, inter)


## 
## The following classes are used to localize or parse variables for the `/userconfig` and `/config` commands
## 

class ConfigVarType(object):
	@classmethod
	@abstractmethod
	async def _localize(cls, value, inter):
		pass

	@classmethod
	@abstractmethod
	async def _parse(cls, value, inter):
		pass

	@classmethod
	async def localize(cls, value, inter):
		return await cls._localize(value, inter)

	@classmethod
	async def parse(cls, value, inter):
		return await cls._parse(value, inter)


class Boolean(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter):
		return "enabled" if value else "disabled"

	@classmethod
	async def _parse(cls, value, inter):
		if value.lower() in [ "enable", "enabled", "true", "yes", "on" ]:
			return True
		elif value.lower() in [ "disable", "disabled", "false", "no", "off" ]:
			return False
		else:
			raise InvalidInputError("Try giving me something like `enable` or `disable`")


class TextChannel(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter):
		return f"<#{value}>" if value else "None"

	@classmethod
	async def _parse(cls, value, inter):
		try:
			channel = await commands.TextChannelConverter().convert(inter, value)
			return channel.id
		except commands.BadArgument:
			raise InvalidInputError("Try giving me a channel reference like `#general`")


class Role(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter):
		return f"<@&{value}>" if value else "None"

	@classmethod
	async def _parse(cls, value, inter):
		try:
			role = await commands.RoleConverter().convert(inter, value)
			return role.id
		except commands.BadArgument:
			raise InvalidInputError("Try giving me a role reference like `@BotAdmin`")


class UserBot(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter):
		return f"<@{value}>" if value else "None"

	@classmethod
	async def _parse(cls, value, inter):
		try:
			user = await commands.UserConverter().convert(inter, value)
			if not user.bot: 
				raise InvalidInputError("The user you give here has to be a bot")
			return user.id
		except commands.BadArgument:
			raise InvalidInputError("Try giving me a bot reference like `@Bot123`")

gtts_langs = read_json(settings.resource("json/gtts_languages.json"))

class GttsLang(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter):
		return gtts_langs[value]

	@classmethod
	async def _parse(cls, value, inter):
		value = value.lower()
		for lang in gtts_langs:
			if lang.lower() == value or gtts_langs[lang].lower() == value:
				if "-" in lang:
					raise InvalidInputError("Languages with '-' have unfortunately been deprecated")
				return lang
		raise InvalidInputError("See https://github.com/mdiller/MangoByte/blob/master/resource/json/gtts_languages.json for valid languages")


class CommandPrefix(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter):
		return value

	@classmethod
	async def _parse(cls, value, inter):
		if len(value) > 5 or len(value) < 1:
			raise InvalidInputError("A command prefix must be between 1 and 5 characters long")
		else:
			return value


class ShortText(ConfigVarType):
	"""Used for introtts and outrotts"""
	@classmethod
	async def _localize(cls, value, inter):
		return value

	@classmethod
	async def _parse(cls, value, inter):
		max_chars = 32
		if len(value) > max_chars:
			raise InvalidInputError(f"Dat text is {len(value)} characters long. This text must be {max_chars} characters or less")
		if value.lower() in [ "nothing", "none", "" ]:
			value = " "
		return value


max_intro_outro_length = 4.5

class ShortClip(ConfigVarType):
	"""Used for intro and outro clips"""
	@classmethod
	async def _localize(cls, value, inter):
		return value

	@classmethod
	async def _parse(cls, value, inter: disnake.Interaction):
		audio_cog = inter.bot.get_cog("Audio")

		value = str(value)
		if value.lower() in [ "none", "silent", "silence", "off", "disable" ]:
			return None
		
		if value.startswith("url:"):
			raise InvalidInputError("Unfortunatley I'm removing the url clip feature for now. I've got plans to eventually implement some custom clips that will be even more flexible than this, but I'm not sure when that feature will arrive.")

		if value.startswith("custom"):
			raise InvalidInputError("You can set a custom clip via the `/customclip` command")


		clip = await audio_cog.get_clip_try_types(value, "local|dota", inter)

		audiolength = clip.audiolength
		if audiolength >  max_intro_outro_length + 0.1:
			raise InvalidInputError(f"Dat clip is {audiolength:.1f} seconds long, and intros/outros gotta be less than {max_intro_outro_length}.")
		return clip.clipid


class SteamId(ConfigVarType):
	@classmethod
	async def _localize(cls, value, inter: disnake.Interaction):
		if value is None:
			return "Not Linked"

		dotastats_cog = inter.bot.get_cog("DotaStats")
		name = "Dota Profile"
		try:
			return await dotastats_cog.get_player_mention(value, inter)
		except UserError:
			return f"[Dota Profile](http://www.opendota.com/players/{value})"

	@classmethod
	async def _parse(cls, value, inter: disnake.Interaction):
		dotastats_cog = inter.bot.get_cog("DotaStats")

		value = str(value)
		if value.lower() in [ "none", "reset", "default" ]:
			return None

		patterns = [
			r"<?https?://(?:www\.)?opendota\.com/players/(\d+)/?>?",
			r"<?https?://(?:www\.)?dotabuff\.com/players/(\d+)/?>?",
			r"<?https?://(?:www\.)?steamcommunity\.com/profiles/(\d+)/?>?"
		]
		for pattern in patterns:
			match = re.match(pattern, value)
			if match:
				value = match.group(1)
				break

		if not value.isdigit():
			raise InvalidInputError("You gotta give me a steam id (SteamId64 / Friend Id) here")
		value = int(value)

		if value > 76561197960265728:
			value -= 76561197960265728

		# This will throw the appropriate UserError if the player is not found / has no matches
		player = await dotastats_cog.get_player_mention(value, inter) # TODO: fix this one

		return value
