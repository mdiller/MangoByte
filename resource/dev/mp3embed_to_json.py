# this script converts the old embedded clipinfo in the local mp3s to the new json format

# note that running this script requires pytaglib, which can be very frustrating to install

import taglib
import os
import re
import json
from collections import OrderedDict

rootdir = "../clips"

def grab_info(filename):
	info = OrderedDict({
		"path": filename[filename.index("/clips/") + 7:]
	})
	if filename[-3:] == "mp3":
		filedata = taglib.File(filename)
		if filedata.tags.get('ARTIST'):
			info["author"] = filedata.tags['ARTIST'][0]
		if filedata.tags.get('SOURCE'):
			info["source"] = filedata.tags['SOURCE'][0]
		if filedata.tags.get('COMMENT'):
			info["text"] = filedata.tags['COMMENT'][0]
	return info

def grab_file_infos(clipinfos):
	for root, dirs, files in os.walk(rootdir):
		for file in files:
			match = re.search(r"^(.+)\.(mp3|wav)$", file)
			if match:
				if match.group(1) not in clipinfos:
					clipinfos[match.group(1)] = grab_info(os.path.join(root, file))

def update_clipinfo(filename):
	data = OrderedDict({})
	if os.path.isfile(filename):
		with open(filename) as f:
			data = json.load(f, object_pairs_hook=OrderedDict)

	grab_file_infos(data)

	text = json.dumps(data, indent="\t")
	with open(filename, "w+") as f:
		f.write(text)
	print(text)

update_clipinfo(f"{rootdir}/clipinfo.json")