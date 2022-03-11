from __main__ import settings
import logging
import logging.handlers
import datetime
import json
import os
import logging_loki
from multiprocessing import Queue

# if we wanna log disnake stuff https://docs.disnake.dev/en/latest/logging.html?highlight=logger
# we can also get the root logger, which will give us a ton of info for all the libraries we have

logging_loki.emitter.LokiEmitter.level_tag = "level"

trace_level = 21
logging.addLevelName(trace_level, "TRACE")
# this log level captures json events that happen during mangobyte
def trace(self, message, *args, **kws):
	if self.isEnabledFor(trace_level):
		# Yes, logger takes its '*args' as 'args'.
		message = json.dumps(message)
		self._log(trace_level, message, args, **kws)
logging.Logger.trace = trace

def setup_logger():
	logger = logging.getLogger("mangologger")

	if settings.debug:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)
		
	# loki handler setup
	loki_handler = setup_loki_handler(settings.loki)
	if loki_handler:
		logger.addHandler(loki_handler)

	# Console Logging
	if settings.debug or loki_handler is None:
		consoleout = logging.StreamHandler()
		logger.addHandler(consoleout)

	return logger

def setup_loki_handler(loki_config):
	if loki_config is None:
		return None

	handler_loki = logging_loki.LokiQueueHandler(
		Queue(-1),
		url=loki_config["url"],
		tags={"application": loki_config["application"]},
		auth=(loki_config["username"], loki_config["password"]),
		version="1",
	)

	# add some checking here to see if its setup or something in future

	return handler_loki