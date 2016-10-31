import os
import sys
import subprocess


def findfile(name, path):
	for root, dirs, files in os.walk(path):
		if name in files:
			return os.path.join(root, name)
	return None

# Gets mangobytes version from git commit number
def get_version():
	return subprocess.check_output(["git", "rev-list", "--count", "master"], stderr=subprocess.STDOUT).decode("utf-8")
