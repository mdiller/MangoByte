from abc import ABCMeta, abstractmethod
from __main__ import settings
from .helpers import *
from gtts import gTTS
import discord
import re
import os
import random
import html

# Clip helper functions
def get_clipfile(clipname):
	for root, dirs, files in os.walk(settings.resourcedir + "clips/"):
		for file in files:
			if re.search("^" + clipname + "\.(mp3|wav)$", file):
				return os.path.join(root, file)
	return None


class ClipNotFound(UserError):
	def __init__(self, cliptype, clipname):
		self.message = "There ain't a {} clip with the name '{}'".format(cliptype, clipname)

class MissingClipType(UserError):
	def __init__(self, clipid):
		self.message = "Yer clipid '{}' is missin a proper cliptype".format(clipid)


class Clip(object):
	def __init__(self, clipname, audiopath, text="", volume=0.6):
		self.name = clipname
		self.audiopath = audiopath
		self.text = text
		self.volume = volume

	@classmethod
	@abstractmethod
	def type(cls):
		pass

	@classmethod
	def types_dict(cls):
		return { cliptype.type(): cliptype for cliptype in cls.__subclasses__() }

	@property
	def clipid(self):
		return "{}:{}".format(self.type(), self.name)

	@property
	def audiolength(self):
		return float(run_command(["ffprobe", "-i", self.audiopath, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"]))

	async def get_info_embed(self, bot):
		description = ""
		if self.text is not None and self.text != "":
			description = self.text
		embed = discord.Embed(description=description)
		embed.set_author(name=self.clipid)
		embed.add_field(name="Clip Length", value="{0:.2f} seconds".format(self.audiolength))
		return embed


class LocalClip(Clip):
	def __init__(self, clipname, bot):
		clipfile = get_clipfile(clipname)
		if clipfile == None:
			raise ClipNotFound(self.type(), clipname)
		Clip.__init__(self, clipname, clipfile)

	@classmethod
	def type(cls):
		return "local"

	async def get_info_embed(self, bot):
		embed = await Clip.get_info_embed(self, bot)
		embed.add_field(name="Section", value=os.path.basename(os.path.dirname(self.audiopath)))
		return embed


class TtsClip(Clip):
	def __init__(self, text, bot):
		tempfile = settings.resourcedir + "temp/" + str(int(random.random() * 1000000000)) + ".mp3"
		tts = gTTS(text=text, lang=settings.ttslang)
		tts.save(tempfile)
		Clip.__init__(self, text, tempfile, text)

	@classmethod
	def type(cls):
		return "tts"


class UrlClip(Clip):
	def __init__(self, url, bot):
		# TODO: add checking for valid url for ffmpeg
		Clip.__init__(self, url, url)

	@classmethod
	def type(cls):
		return "url"

	async def get_info_embed(self, bot):
		embed = await Clip.get_info_embed(self, bot)
		embed.url = self.audiopath
		return embed


class DotaClip(Clip):
	def __init__(self, responsename, bot):
		dotabase = bot.get_cog("Dotabase")
		self.response = dotabase.get_response(responsename)
		if self.response == None:
			raise ClipNotFound(self.type(), responsename)
		Clip.__init__(self, responsename, dotabase.vpkurl + self.response.mp3, text=self.response.text, volume=0.4)

	@classmethod
	def type(cls):
		return "dota"

	async def get_info_embed(self, bot):
		dotabase = bot.get_cog("Dotabase")

		embed = await Clip.get_info_embed(self, bot)
		embed.set_author(name=self.name, icon_url=await dotabase.get_hero_icon(self.response.hero_id))
		embed.url = self.audiopath
		if self.response.criteria != "":
			embed.add_field(inline=False, name="Criteria", value=self.response.criteria.replace("|", "\n"))

		return embed


