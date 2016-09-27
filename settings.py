import json

# This module provides a simple way to interface with the settings.json file.
# it reads the file when the module loads and stores the variables in variables that are globally visible


# Open settings file
with open('settings.json') as settings_file:
	settings_data = json.load(settings_file)

token = settings_data["token"]
resourcedir = settings_data["resourcedir"]
dotavpk = settings_data["dotavpk"]
defaultvoice = settings_data["defaultvoice"]
steamapikey = settings_data["steamapikey"]