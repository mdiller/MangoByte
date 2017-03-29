import os
import sys
import json
import subprocess
from collections import OrderedDict

def findfile(name, path):
	for root, dirs, files in os.walk(path):
		if name in files:
			return os.path.join(root, name)
	return None

def run_command(commandarray):
	return subprocess.check_output(commandarray, stderr=subprocess.STDOUT).decode("utf-8")

# Gets mangobytes version from git commit number
def get_version():
	return run_command(["git", "rev-list", "--count", "master"])

def get_changelog():
	return run_command(["git", "log", "-n", "5", "--pretty=%H,%cd,%h,%s", "--date=unix"])

def write_json(filename, data):
	text = json.dumps(data, indent="\t")
	with open(filename, "w+") as f:
		f.write(text) # Do it like this so it doesnt break mid-file

def read_json(filename):
	with open(filename) as f:
		return json.load(f, object_pairs_hook=OrderedDict)


class UserError(Exception):
	def __init__(self, message):
		self.message = message