from abc import ABCMeta, abstractmethod
from __main__ import settings
from .helpers import *
from gtts import gTTS
import re
import os
import random

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


class LocalClip(Clip):
	def __init__(self, clipname, bot):
		clipfile = get_clipfile(clipname)
		if clipfile == None:
			raise ClipNotFound(self.type(), clipname)
		Clip.__init__(self, clipname, clipfile)

	@classmethod
	def type(cls):
		return "local"


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


class DotaClip(Clip):
	def __init__(self, responsename, bot):
		dotabase = bot.get_cog("Dotabase")
		response = dotabase.get_response(responsename)
		if response == None:
			raise ClipNotFound(self.type(), responsename)
		Clip.__init__(self, responsename, dotabase.vpkurl + response.mp3, text=response.text, volume=0.4)

	@classmethod
	def type(cls):
		return "dota"


async def get_clip(clipid, bot):
	cliptypes = Clip.types_dict()

	match = re.search("^(" + "|".join(cliptypes) + "):(.*)$", clipid)

	if not match:
		raise MissingClipType(clipid)

	return cliptypes[match.group(1)](match.group(2), bot)


async def play_clip(clip, bot):
	if isinstance(clip, str):
		clip = await get_clip(clip, bot)

	audio = bot.get_cog("Audio")
	await audio.queue_clip(clip)

