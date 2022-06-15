import re
import datetime
from io import BytesIO
from tinydb import TinyDB, Query

from utils.tools.helpers import *
from utils.tools.logger import logger
from utils.tools.settings import settings

default_cache = { "count": 0, "files": {} }

# EXAMPLE CACHE ITEM
# {
# 	"key": "<the cache key>",
# 	"file": "<filename>",
# 	"timestamp": "<last time this file was visited>"
# }
CacheItem = Query()

def get_timestamp(date=None):
	if date is None:
		date = datetime.datetime.now()
	return int(datetime.datetime.timestamp(date) * 1000)

class Cache:
	def __init__(self, loop):
		self.loop = loop
		self.cache_dir = settings.resource("cache/")
		self.db = TinyDB(self.cache_dir + "_cache_tinydb.json")
		self.lock = asyncio.Lock(loop=self.loop)

	@property # TODO: PROLLY REMOVE
	def files(self):
		return self.cache["files"]

	# Returns the filename of the cached url if it exists, otherwise None
	async def get_filename(self, uri):
		async with self.lock:
			item = self.db.get(CacheItem.key == uri)
			if item is None:
				return None
			filename = self.cache_dir + item["file"]
		if not os.path.isfile(filename):
			return None
		return filename

	# Returns the file if it exists, otherwise None
	async def get(self, uri, return_type):
		filename = await self.get_filename(uri)
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
		filename = await self.get_filename(uri)
		if filename is not None:
			return filename
		async with self.lock:
			filename = f"{len(self.db):0>4}"
			if extension:
				filename = f"{filename}.{extension}"
			self.db.upsert({
				"key": uri,
				"file": filename,
				"timestamp": get_timestamp()
			}, CacheItem.key == uri)
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
			item = self.db.get(CacheItem.key == uri)
			if item is not None:
				filename = self.cache_dir + item["file"]
				if os.path.isfile(filename):
					os.remove(filename)
				self.db.remove(doc_ids=[item.doc_id])