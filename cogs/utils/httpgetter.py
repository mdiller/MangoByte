from .helpers import *
import discord
import aiohttp
from io import BytesIO

default_error = "Http request failed with a {} error"


class HttpGetter:
	def __init__(self):
		self.loop = asyncio.get_event_loop()
		self.session = aiohttp.ClientSession(loop=self.loop)


	async def get(self, url, return_type="json", cache=False, errors={}):
		async with self.session.get(url) as r:
			if r.status == 200:
				if return_type == "json":
					return json.loads(await r.text(), object_pairs_hook=OrderedDict)
				elif return_type == "text":
					return await r.text()
				elif return_type == "bytes":
					return BytesIO(await r.read())
				else:
					raise ValueError(f"Invalid return type '{return_type}'")

			elif r.status == 404:
				raise Http404Error(status_errors.get(404, default_error))
			else:
				raise HttpError(status_errors.get(r.status, default_error), r.status)

	


