from __main__ import settings
from .helpers import *
import re
import aiohttp
from io import BytesIO

default_error = "Http request failed with a {} error"
default_cache = { "count": 0, "files": {} }

class Cache:
	def __init__(self, loop):
		self.loop = loop
		self.cache_dir = settings.resource("cache/")
		self.index_file = self.cache_dir + "cache_index.json"
		self.cache = {}
		self.lock = asyncio.Lock(loop=self.loop)
		if os.path.isfile(self.index_file):
			self.cache = read_json(self.index_file)
		for key in default_cache:
			if key not in self.cache:
				self.cache[key] = default_cache[key]
		self.save_cache()

	@property
	def files(self):
	    return self.cache["files"]

	def save_cache(self):
		if not os.path.exists(self.cache_dir):
			os.makedirs(self.cache_dir)
		write_json(self.index_file, self.cache)

	# Returns the filename of the cached url if it exists, otherwise None
	def get_filename(self, url):
		if url not in self.files:
			return None
		filename = self.cache_dir + self.files[url]
		if not os.path.isfile(filename):
			return None
		return filename

	# Returns the file if it exists, otherwise None
	def get(self, url, return_type):
		filename = self.get_filename(url)
		if not filename:
			return None
		if return_type == "json":
			return read_json(filename)
		elif return_type == "text":
			with open(filename, "r") as f:
				return f.read()
		elif return_type == "bytes":
			with open(filename, "rb") as f:
				return BytesIO(f.read())
		else:
			raise ValueError(f"Invalid return type '{return_type}'")

	async def save(self, url, return_type, response):
		with (await self.lock):
			filename = f"{self.cache['count']:0>4}"
			if return_type == "json":
				filename += ".json"
			elif return_type == "text":
				filename += ".txt"
			elif return_type == "bytes":
				match = re.search(r"(\.[a-z0-9]{1,6})$", url.lower())
				if match:
					filename += match.group(1)
			else:
				raise ValueError(f"Invalid return type '{return_type}'")

			with open(self.cache_dir + filename, "wb+") as f:
				f.write(await response.read())

			self.files[url] = filename
			self.cache["count"] += 1
			self.save_cache()

	async def remove(self, url):
		with (await self.lock):
			filename = self.cache_dir + self.files.pop(url)
			self.save_cache()
			if os.path.isfile(filename):
				os.remove(filename)


class HttpGetter:
	def __init__(self):
		self.loop = asyncio.get_event_loop()
		self.session = aiohttp.ClientSession(loop=self.loop)
		self.cache = Cache(self.loop)

	async def get(self, url, return_type="json", cache=False, errors={}):
		if cache and self.cache.get_filename(url):
			return self.cache.get(url, return_type)

		async with self.session.get(url) as r:
			if r.status == 200:
				if cache:
					await self.cache.save(url, return_type, r)

				if return_type == "json":
					return json.loads(await r.text(), object_pairs_hook=OrderedDict)
				elif return_type == "text":
					return await r.text()
				elif return_type == "bytes":
					return BytesIO(await r.read())
				else:
					raise ValueError(f"Invalid return type '{return_type}'")

			elif r.status == 404:
				raise Http404Error(errors.get(404, default_error))
			else:
				raise HttpError(errors.get(r.status, default_error), r.status)




