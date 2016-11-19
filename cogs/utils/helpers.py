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

def get_changelog(count):
	return run_command(["git", "log", "-n", str(count), "--pretty=**%cd** %s", "--date=format:%b %d, %I:%M%p"])

def audio_length(filename):
	return float(run_command(["ffprobe", "-i", filename, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"]))

def write_json(filename, data):
	with open(filename, "w+") as f:
		json.dump(data, f, indent="\t")

def read_json(filename):
	with open(filename) as f:
		return json.load(f, object_pairs_hook=OrderedDict)