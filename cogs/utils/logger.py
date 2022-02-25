from __main__ import settings
import logging
import datetime
import os
from pythonjsonlogger import jsonlogger

# if we wanna log disnake stuff https://docs.disnake.dev/en/latest/logging.html?highlight=logger
# we can also get the root logger, which will give us a ton of info for all the libraries we have

if not os.path.exists("logs"):
    os.makedirs("logs")

def setup_logger():
	logger = logging.getLogger("mangologger")

	if settings.debug:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)

	# Console Logging
	if settings.debug:
		consoleout = logging.StreamHandler()
		logger.addHandler(consoleout)

	# JSON file logging
	timestamp = datetime.datetime.now().strftime("%Y-%m-%d__%I_%M%p")
	filehandler = logging.FileHandler(filename=f"logs/mangolog_{timestamp}.log", encoding="utf-8", mode="w")
	
	jsonformatter = jsonlogger.JsonFormatter()
	filehandler.setFormatter(jsonformatter)

	logger.addHandler(filehandler)


	return logger