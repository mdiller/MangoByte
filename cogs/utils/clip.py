from abc import ABCMeta, abstractmethod
from __main__ import settings, botdata, httpgetter
from .helpers import *
from gtts import gTTS
import urllib.request
import discord
import re
import os
import random
import html
import requests

def tts_save(filename, text, lang="en-au"):
	# run_command(["pico2wave", "--wave", filename, "-l", "en-GB", text])
	try:
		tts = gTTS(text=text, lang=lang)
		tts.save(filename)
	except AttributeError:
		raise UserError("Whoops. Looks like gtts is broken right now.")
	except (RecursionError, requests.exceptions.HTTPError):
		raise UserError("There was a problem converting that via gtts")

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
		return round(float(run_command(["ffprobe", "-i", self.audiopath, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"])), 2)

	async def get_info(self):
		return self.text if self.text is not None else ""


class LocalClip(Clip):
	def __init__(self, clipname, bot, ctx):
		audio = bot.get_cog("Audio")
		clipinfos = audio.local_clipinfo

		if not clipname in clipinfos:
			raise ClipNotFound(self.type, clipname)

		info = clipinfos[clipname]
		self.author = info.get("author")
		self.source = info.get("source")
		self.tags = info.get("tags")
		if self.tags:
			self.tags = self.tags.split("|")

		text = info.get("text", "")
		clipfile = settings.resource("clips/" + info.get("path"))

		Clip.__init__(self, clipname, clipfile, text=text)

	@classmethod
	def type(cls):
		return "local"

	async def get_info(self):
		result = ""
		if self.text != "":
			result += f"\"{self.text}\""
		if self.author:
			if self.text != "":
				result += f" - {self.author}"
			else:
				result += f"By {self.author}"
		if self.author or self.text != "":
			result += "\n\n"
		if self.source:
			result += f"**Source:** {self.source}\n"
		if self.tags:
			result += f"*Tags: {', '.join(self.tags)}*"
		return result



class TtsClip(Clip):
	def __init__(self, text, bot, ctx):
		tempfile = settings.resource("temp/{}.wav".format(int(random.random() * 1000000000)))
		data = botdata.guildinfo(ctx)
		if data:
			tts_save(tempfile, text, data.ttslang)
		else:
			tts_save(tempfile, text)
		Clip.__init__(self, text, tempfile, text)

	@classmethod
	def type(cls):
		return "tts"


class UrlClip(Clip):
	def __init__(self, url, bot, ctx):
		# TODO: add checking for valid url for ffmpeg
		url = re.sub(r"^https://", "http://", url)
		if not re.match(r'^https?://.*\.(mp3|wav)$', url):
			raise UserError("That's not a valid mp3 or wav url")
		try:
			urllib.request.urlopen(url)
		except (urllib.error.URLError, urllib.error.HTTPError):
			raise UserError("There was a problem opening this URL")
		Clip.__init__(self, url, url)

	@classmethod
	def type(cls):
		return "url"

class DotaClip(Clip):
	def __init__(self, responsename, bot, ctx):
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

gtts_langs = read_json(settings.resource("json/gtts_languages.json"))

class GttsLang():
	def __init__(self, language):
		language = language.lower()
		self.lang = None
		for lang in gtts_langs:
			if lang.lower() == language or gtts_langs[lang].lower() == language:
				self.lang = lang
		if self.lang is None:
			raise ValueError(f"'{language}' is not a valid gtts lang")

	@property
	def pretty(self):
		return gtts_langs[self.lang]

	def __repr__(self):
		return self.lang

	@classmethod
	def get(cls, language):
		try:
			return GttsLang(language)
		except ValueError:
			return None
