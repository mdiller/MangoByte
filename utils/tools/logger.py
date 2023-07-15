import json
import copy
import logging
import asyncio
import aiohttp
import logging.handlers
from multiprocessing import Queue
from typing import OrderedDict, List, Dict, Tuple, TypedDict, Optional
from aiohttp.client_exceptions import ClientConnectorError

from utils.tools.settings import settings

MANGO_LOGGER_NAME = "mangologger"

# if we wanna log disnake stuff https://docs.disnake.dev/en/latest/logging.html?highlight=logger
# we can also get the root logger, which will give us a ton of info for all the libraries we have

trace_level = 21
logging.addLevelName(trace_level, "TRACE")
# this log level captures json events that happen during mangobyte
def trace(self, message, *args, **kws):
	if self.isEnabledFor(trace_level):
		message = json.dumps(message)
		self._log(trace_level, message, args, **kws)
logging.Logger.trace = trace

def event(self, type, data = {}):
	if self.isEnabledFor(trace_level):
		data = OrderedDict(data)
		data["type"] = type
		data.move_to_end("type", last=False)
		message = json.dumps(data)
		self._log(trace_level, message, [])
logging.Logger.event = event

# creates an event object but at the "info" level, so it gets deleted after 30 days
def event_info(self, type, data = {}):
	if self.isEnabledFor(logging.INFO):
		data = OrderedDict(data)
		data["type"] = type
		data.move_to_end("type", last=False)
		message = json.dumps(data)
		self._log(logging.INFO, message, [])
logging.Logger.event_info = event_info

def setup_logger():
	logger = logging.getLogger(MANGO_LOGGER_NAME)

	if settings.debug:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)
		
	return logger

def get_full_class_name(obj):
	module = obj.__class__.__module__
	if module is None or module == str.__class__.__module__:
		return obj.__class__.__name__
	return module + '.' + obj.__class__.__name__


# LOKI LOGGING STUFF
# The below was heavily inspired by https://github.com/AXVin/aioloki

class CustomQueue(asyncio.Queue):
	# places an item at the front of the queue
	def put_front_nowait(self, item):
		if self.full():
			raise asyncio.QueueFull
		self._queue.appendleft(item)
		self._unfinished_tasks += 1
		self._finished.clear()
		self._wakeup_next(self._getters)

class LokiStream(TypedDict):
	stream: Dict[str, str]
	values: List[Tuple[str, str]]

class LokiPayload(TypedDict):
	streams: List[LokiStream]

class AioLokiHandler(logging.Handler):
	def __init__(
		self,
		url: str,
		/, *,
		session: aiohttp.ClientSession,
		tags: Optional[Dict[str, str]]=None,
	) -> None:
		super().__init__()
		self._queue: CustomQueue[logging.LogRecord] = CustomQueue()
		self.url = url + "/loki/api/v1/push"
		self.session = session
		self.tags = tags
		self._task = asyncio.create_task(self._queue_worker())

	async def _queue_worker(self):
		try:
			while True:
				log = await self._queue.get()
				payload = self.build_payload(log)
				try:
					async with self.session.post(self.url, json=payload) as response:
						if response.status == 400:
							print("LOKI LOGGER SAID WE HAD INVALID PACKET (response code 400), SKIPPING THIS ONE.")
						elif response.status != 204:
							print("LOKI LOGGER bad response: ", response.status)
							print("Sleeping 1 min before retrying")
							self._queue.put_front_nowait(log)
							await asyncio.sleep(60)
				except asyncio.TimeoutError: # if we get a timeout error, dont break our loop. re-add the log to the queue and keep goin.
					print("LOKI LOGGER TimeoutError. Re-trying...")
					self._queue.put_front_nowait(log)
				except ClientConnectorError as e:
					print(f"LOKI LOGGER ClientConnectorError: {e}")
					print("Sleeping 1 min before retrying")
					self._queue.put_front_nowait(log)
					await asyncio.sleep(60)

		except asyncio.CancelledError as e:
			print("LOKI LOGGER CANCELLED")
		except Exception as e:
			print(f"LOKI LOGGER BROKE: [{get_full_class_name(e)}]: {e}")

	def build_tags(self, log: logging.LogRecord, /):
		tags = copy.deepcopy(self.tags) or {}
		if log.name.startswith("disnake"):
			log.msg = f"DISNAKE({log.name}): " + log.msg
			log.name = MANGO_LOGGER_NAME
		tags["level"] = log.levelname.lower()
		tags["logger"] = log.name
		try:
			extra_tags = log.tags # type: ignore
		except AttributeError:
			pass
		else:
			tags.update(extra_tags)
		return tags

	def build_payload(self, log: logging.LogRecord, /) -> LokiPayload:
		labels = self.build_tags(log)
		return {
			"streams": [{
				"stream": labels,
				"values": [
					(str(int(log.created * 1e9)), self.format(log))
				]
			}]
		}

	def emit(self, record: logging.LogRecord) -> None:
		self._queue.put_nowait(record)

# call this to initialize the logger once the loop has been created
async def init_logger():
	loki_config = settings.loki
	logger = logging.getLogger(MANGO_LOGGER_NAME)
	
	if settings.debug or loki_config is None:
		consoleout = logging.StreamHandler()
		logger.addHandler(consoleout)

	if loki_config is None:
		return None

	baseurl = loki_config["base_url"]

	loop = asyncio.get_event_loop()
	session = aiohttp.ClientSession(loop=loop, auth=aiohttp.BasicAuth(loki_config["username"], loki_config["password"]))
	handler = AioLokiHandler(
		baseurl,
		tags={"application": loki_config["application"]},
		session=session
	)

	disnake_logger = logging.getLogger("disnake")
	disnake_logger.setLevel(logging.INFO)

	rootlogger = logging.getLogger("root")
	logger.addHandler(handler)
	rootlogger.addHandler(handler)
	disnake_logger.addHandler(handler)

logger = setup_logger()
