from .helpers import *
import os
from collections import OrderedDict

#
# loosely based off of the red discord bot's settings
# to import from mangobyte.py, use:
# from __main__ import settings
#

class Settings:
	def __init__(self):
		self.path = "settings.json"
		self.defaults = OrderedDict([  ("token", ""), ("resourcedir", "resource/"), ("dotavpk", ""), ("defaultvoice", ""), ("steamapikey", "") ])
		if not os.path.exists(self.path):
			self.json_data = self.defaults
			self.save_settings()
		else:
			current = read_json(self.path)
			if current.keys() != self.defaults.keys():
				for key in self.defaults.keys():
					if key not in current.keys():
						current[key] = self.defaults[key]
						print("Adding " + str(key) + " field to settings.json")
				write_json(self.path, current)
			self.json_data = read_json(self.path)

	def save_settings(self):
		write_json(self.path, self.json_data)

	@property
	def token(self):
		return self.json_data["token"]

	@property
	def resourcedir(self):
		return self.json_data["resourcedir"]

	@property
	def dotavpk(self):
		return self.json_data["dotavpk"]

	@property
	def defaultvoice(self):
		return self.json_data["defaultvoice"]

	@property
	def steamapikey(self):
		return self.json_data["steamapikey"]

