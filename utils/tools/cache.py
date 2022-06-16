import re
import datetime
import uuid
from io import BytesIO
from disnake.ext import tasks
from tinydb import TinyDB, Query, middlewares
from tinydb.storages import JSONStorage

from utils.tools.helpers import *
from utils.tools.logger import logger
from utils.tools.settings import settings


# a middleware we can use to delay flushing till its needed. ie: dont write on every query
class DelayedStorageMiddleware(middlewares.Middleware):
	def __init__(self, storage_cls):
		super().__init__(storage_cls)
		self.cache = None

	def read(self):
		if self.cache is None:
			self.cache = self.storage.read()
		return self.cache

	def write(self, data):
		self.cache = data

	# actually write data to disk
	def flush(self):
		self.storage.write(self.cache)

	def close(self):
		self.flush()
		self.storage.close()

# EXAMPLE CACHE ITEM
# {
# 	"key": "<the cache key>",
# 	"file": "<filename>",
# 	"timestamp": "<last time this file was visited>"
# }
CacheItem = Query()

# currently set to 1 week timeout for cache files
CACHE_FILE_TIMEOUT_MS = 1000 * 60 * 60 * 24 * 7

def get_timestamp(date=None):
	if date is None:
		date = datetime.datetime.now()
	return int(datetime.datetime.timestamp(date) * 1000)

class Cache:
	def __init__(self, loop):
		self.loop = loop
		self.cache_dir = settings.resource("cache/")
		if not os.path.exists(self.cache_dir):
			os.makedirs(self.cache_dir)
		self.db = TinyDB(self.cache_dir + "_cache_db.json", storage=DelayedStorageMiddleware(JSONStorage))
		self.lock = asyncio.Lock(loop=self.loop)
	
	@property
	def size(self):
		return len(self.db)
	
	# Cleans up any old files and flushes the cache to disk
	@tasks.loop(hours=4)
	async def cleanup_and_flush(self):
		threshold = get_timestamp() - CACHE_FILE_TIMEOUT_MS
		async with self.lock:
			timer = SimpleTimer()
			expired_items = self.db.search(CacheItem.timestamp < threshold)
			expired_item_ids = list(map(lambda item: item.doc_id, expired_items))
			for item in expired_items:
				filename = self.cache_dir + item["file"]
				if os.path.isfile(filename):
					os.remove(filename)
			self.db.remove(doc_ids=expired_item_ids)
			self.db.storage.flush()
			logger.info(f"{len(expired_item_ids)} culled from cache in {timer.miliseconds}ms. New cache size {self.size}")

	# Returns the filename of the cached url if it exists, otherwise None
	async def get_filename(self, uri):
		async with self.lock:
			item = self.db.get(CacheItem.key == uri)
			if item is None:
				return None
			self.db.update({"timestamp": get_timestamp()}, doc_ids=[item.doc_id])
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
		async with self.lock:
			item = self.db.get(CacheItem.key == uri)
			if item is not None:
				filename = self.cache_dir + item["file"]
				if os.path.isfile(filename):
					return filename
			filename = str(uuid.uuid4())
			if extension:
				filename = f"{filename}.{extension}"
			self.db.upsert({
				"key": uri,
				"file": filename,
				"timestamp": get_timestamp()
			}, CacheItem.key == uri)
			self.db.storage.flush()
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