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
from concurrent.futures import ThreadPoolExecutor

def tts_save(filename, text, lang):
	# run_command(["pico2wave", "--wave", filename, "-l", "en-GB", text])
	try:
		tts = gTTS(text=text, lang=lang)
		tts.save(filename)
	except AttributeError:
		raise UserError("Whoops. Looks like gtts is broken right now.")
	except (RecursionError, requests.exceptions.HTTPError):
		raise UserError("There was a problem converting that via gtts")
	except AssertionError as e:
		if e.args and e.args[0] == "No text to send to TTS API":
			raise UserError("I can't convert that to TTS. Looks like there's not much there.")
		else:
			raise

class ClipNotFound(UserError):
	def __init__(self, cliptype, clipname):
		super().__init__("There ain't a {} clip with the name '{}'".format(cliptype, clipname))

class MissingClipType(UserError):
	def __init__(self, clipid):
		super().__init__("Yer clipid '{}' is missin a proper cliptype".format(clipid))

# For this class and all its subclasses, we need to have
# init be asynchronous. because of this, we are simply making
# it a method that should always be called after initializing
# the object. therefore, to initialize a clip, do something
# like this:
# await Clip().init(<stuffhere>)
# instead of:
# Clip(<stuffhere>)

class Clip(object):
	async def init(self, clipname, audiopath, text="", volume=0.6):
		self.name = clipname
		self.audiopath = audiopath
		self.text = text
		self.volume = volume
		return self

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

	async def get_info_embed(self):
		embed = discord.Embed()
		embed.description = self.text if self.text is not None else ""
		self.add_info_embed_parts(embed)
		return embed

	def add_info_embed_parts(self, embed):
		"""Adds some things to a clips `info` embed"""
		embed.set_author(name=self.clipid)
		embed.add_field(name="Length", value=f"{self.audiolength} seconds")


class LocalClip(Clip):
	async def init(self, clipname, bot, ctx):
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

		return await Clip.init(self, clipname, clipfile, text=text)

	@classmethod
	def type(cls):
		return "local"

	async def get_info_embed(self):
		result = ""
		if self.text != "":
			result += f"\"{self.text}\""
		if self.author:
			if self.text != "":
				result += f" - {self.author}"
			else:
				result += f"By {self.author}"
		embed = discord.Embed()
		embed.description = result
		if self.source:
			embed.add_field(name="Source", value=self.source)
		if self.tags:
			embed.add_field(name="Tags", value=", ".join(self.tags))
		self.add_info_embed_parts(embed)
		return embed



class TtsClip(Clip):
	async def init(self, text, bot, ctx):
		data = botdata.guildinfo(ctx)
		ttslang = "en-au" if not data else data.ttslang
		uri = f"clip_tts_{ttslang}:{text}"

		filename = httpgetter.cache.get_filename(uri)
		if not filename:
			filename = await httpgetter.cache.new(uri, "wav")
			try:
				await bot.loop.run_in_executor(ThreadPoolExecutor(max_workers=1), tts_save, filename, text, ttslang)
			except:
				await httpgetter.cache.remove(uri)
				raise
		return await Clip.init(self, text, filename, text)

	@classmethod
	def type(cls):
		return "tts"


class UrlClip(Clip):
	async def init(self, url, bot, ctx):
		if not re.match(f'^https?://.*\.({audio_extensions})$', url):
			raise UserError("That's not a valid audio url")

		filename = await httpgetter.get(url, "filename", cache=True)
		return await Clip.init(self, url, filename)

	@classmethod
	def type(cls):
		return "url"

class DotaClip(Clip):
	async def init(self, responsename, bot, ctx):
		dotabase = bot.get_cog("Dotabase")
		self.response = dotabase.get_response(responsename)
		if self.response == None:
			raise ClipNotFound(self.type(), responsename)
		self.voice_thumbnail = None
		if self.response.voice.image:
			self.voice_thumbnail = dotabase.vpkurl + self.response.voice.image

		filename = await httpgetter.get(dotabase.vpkurl + self.response.mp3, "filename", cache=True)
		return await Clip.init(self, responsename, filename, text=self.response.text, volume=0.4)

	@classmethod
	def type(cls):
		return "dota"

	async def get_info_embed(self):
		embed = discord.Embed()
		embed.description = f"\"{self.response.text}\" - {self.response.voice.name}"
		if self.response.criteria != "":
			embed.add_field(name="Criteria", value=self.response.pretty_criteria.replace('|', '\n'))
		if self.response.voice.voice_actor:
			embed.add_field(name="Voice Actor", value=self.response.voice.voice_actor)
		if self.voice_thumbnail:
			embed.set_thumbnail(url=self.voice_thumbnail)

		self.add_info_embed_parts(embed)
		return embed

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
