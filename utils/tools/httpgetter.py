from math import perm
import re
from io import BytesIO

import aiohttp
from utils.tools.helpers import *
from utils.tools.logger import logger
from utils.tools.settings import settings
from utils.tools.cache import Cache

def raise_error(url, code, errors):
	template = errors.get(code, errors.get("default", "Http request failed with a {} error"))
	if code == 404:
		raise Http404Error(template, url)
	else:
		logger.error(f"http {code} error on: {url}")
		raise HttpError(template, url, code)

class HttpGetter:
	def __init__(self):
		self.loop = asyncio.get_event_loop()
		self.session = aiohttp.ClientSession(loop=self.loop)
		self.cache = Cache(self.loop)

	async def get(self, url, return_type="json", cache=False, cache_permanent=False, errors={}, headers=None):
		if cache_permanent:
			cache = True
		if cache and await self.cache.get_filename(url):
			return await self.cache.get(url, return_type)

		timer = SimpleTimer()
		async with self.session.get(url, headers=headers, timeout=60) as r:
			logger.event("httprequest", {
				"url": url,
				"status": r.status,
				"time": timer.miliseconds
			})
			if r.status == 200:
				if cache:
					await self.cache.save(url, return_type, r, permanent=cache_permanent)
					if return_type == "filename":
						return await self.cache.get_filename(url)

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
		timer = SimpleTimer()
		async with self.session.post(url, json=body, headers=headers) as r:
			logger.event("httprequest", {
				"url": url,
				"status": r.status,
				"time": timer.miliseconds,
				"method": "POST"
			})
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

httpgetter = HttpGetter()


