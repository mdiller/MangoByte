from mangobyte import settings, loggingdb
from .helpers import *
import re
import aiohttp
from io import BytesIO

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
	def get_filename(self, uri):
		if uri not in self.files:
			return None
		filename = self.cache_dir + self.files[uri]
		if not os.path.isfile(filename):
			return None
		return filename

	# Returns the file if it exists, otherwise None
	def get(self, uri, return_type):
		filename = self.get_filename(uri)
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
		elif return_type == "filename":
			return filename
		else:
			raise ValueError(f"Invalid return type '{return_type}'")

	#creates a new entry in the cache and returns the filename of the new entry
	async def new(self, uri, extension=None):
		async with self.lock:
			if uri in self.files:
				return self.cache_dir + self.files[uri]
			filename = f"{self.cache['count']:0>4}"
			if extension:
				filename = f"{filename}.{extension}"
			self.files[uri] = filename
			self.cache["count"] += 1
			self.save_cache()
		return self.cache_dir + filename


	async def save(self, url, return_type, response):
		extension = None
		if return_type == "json":
			extension = "json"
		elif return_type == "text":
			extension = "txt"
		elif return_type in ["filename", "bytes"]:
			match = re.search(r"\.([a-z0-9]{1,6})$", url.lower())
			if match:
				extension = match.group(1)
		else:
			raise ValueError(f"Invalid return type '{return_type}'")

		filename = await self.new(url, extension)
		with open(filename, "wb+") as f:
			f.write(await response.read())


	async def remove(self, uri):
		async with self.lock:
			if uri in self.files:
				filename = self.cache_dir + self.files.pop(uri)
				self.save_cache()
				if os.path.isfile(filename):
					os.remove(filename)

def raise_error(url, code, errors):
	print(f"http {code} error on: {url}")
	template = errors.get(code, errors.get("default", "Http request failed with a {} error"))
	if code == 404:
		raise Http404Error(template)
	else:
		raise HttpError(template, code)

class HttpGetter:
	def __init__(self):
		self.loop = asyncio.get_event_loop()
		self.session = aiohttp.ClientSession(loop=self.loop)
		self.cache = Cache(self.loop)

	async def get(self, url, return_type="json", cache=False, errors={}):
		if cache and self.cache.get_filename(url):
			return self.cache.get(url, return_type)

		async with self.session.get(url, timeout=60) as r:
			await loggingdb.insert_http_request(url, r.status, cache)
			if r.status == 200:
				if cache:
					await self.cache.save(url, return_type, r)
					if return_type == "filename":
						return self.cache.get_filename(url)

				if return_type == "json":
					return json.loads(await r.text(), object_pairs_hook=OrderedDict)
				elif return_type == "text":
					return await r.text()
				elif return_type == "bytes":
					return BytesIO(await r.read())
				else:
					raise ValueError(f"Invalid return type '{return_type}'")
			else:
				raise_error(url, r.status, errors)

	async def post(self, url, return_type="json", errors={}, body={}, headers={}):
		async with self.session.post(url, json=body, headers=headers) as r:
			await loggingdb.insert_http_request(url, r.status, False)
			if r.status == 200:
				if return_type == "json":
					return json.loads(await r.text(), object_pairs_hook=OrderedDict)
				elif return_type == "text":
					return await r.text()
				elif return_type == "bytes":
					return BytesIO(await r.read())
				else:
					raise ValueError(f"Invalid return type '{return_type}'")
			else:
				raise_error(url, r.status, errors)




