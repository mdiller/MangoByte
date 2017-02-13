from abc import ABCMeta, abstractmethod
from __main__ import settings
from .helpers import *
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

def tts_save(filename, text):
	run_command(["pico2wave", "--wave", filename, "-l", "en-GB", text])

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

	async def get_info(self):
		return self.text if self.text is not None else ""


class LocalClip(Clip):
	def __init__(self, clipname, bot):
		clipfile = get_clipfile(clipname)
		if clipfile == None:
			raise ClipNotFound(self.type(), clipname)
		Clip.__init__(self, clipname, clipfile)

	@classmethod
	def type(cls):
		return "local"

	async def get_info(self):
		return "From the '{}' section".format(os.path.basename(os.path.dirname(self.audiopath)))


class TtsClip(Clip):
	def __init__(self, text, bot):
		tempfile = "{}temp/{}.wav".format(settings.resourcedir, int(random.random() * 1000000000))
		tts_save(tempfile, text)
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

	async def get_info(self):
		text = "\"{0}\" - {1}".format(self.response.text, self.response.hero.localized_name)
		if self.response.criteria != "":
			text += "\n\n*"
			text += self.response.pretty_criteria
			text += "*"

		return text


