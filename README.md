# MangoByte<img align="right" src="mangobyte.png"/>
A discord bot that provides the ability to play audio clips, play dota responses, answer questions, randomly react to messages, and a few other cool things. I'm using the [discord.py](https://github.com/Rapptz/discord.py) python wrapper for the [Discord API](https://discordapp.com/developers). I'm also making use of [dotabase](https://github.com/mdiller/dotabase), which is an open source repository (created by yours truly) containing data about the game [Dota 2](http://www.dota2.com).

## Commands
The following is a list of most of the commands that mangobyte has to offer

   Command|Description
----------|---
ask       |Answers any question you might have
play      |Plays an audio clip
stop      |Stops the currently playing audio
tts       |Like ?echo but for people who can't read
setintro  |Sets your intro clip
playurl   |Plays an mp3 file at a url
replay    |Replays the last played clip
clipinfo  |Gets info about the indicated clip
playlist  |Lists the audio clips available for ?play
lastgame  |Gets info about your last dota game
setsteam  |Links a discord user to their steam/dota accont
whois     |Displays information about the user's dota profile
dota      |Plays a dota response
no        |Nopes.
yes       |Oooooh ya.
thanks    |Gives thanks
inthebag  |Proclaims that 'IT' (whatever it is) is in the bag
hello     |Says hello
lol       |WOW I WONDER WAT THIS DOES
ping      |Pings a number of times(within reason)
lasagna   |A baked Italian dish
changelog |Gets a rough changelog for mangobyte
echo      |Echo...
info      |Prints info about mangobyte
help      |Prints a help message with a list of all of the commands

## Installation

Before installing and running your own instance of mangobyte, you will first need to install the following:

* Python 3.5
* Pip
* PicoTTS (run `sudo apt-get libttspico-utils`)
* [dotabase](https://github.com/mdiller/dotabase)
* [discord.py](https://github.com/Rapptz/discord.py)

Now make sure to run `python3.5 -m pip install -r requirements.txt` to install the rest of the needed packages.

If you run `python3.5 mangobyte.py`, you will probably get an error message because the bot token isn't set. You'll have to [create a bot account](https://twentysix26.github.io/Red-Docs/red_guide_bot_accounts/) through discord and then set the `token` field in the `settings.json` file to your new bot's token. After you have done this, and have invited your bot to your server, dont forget to add the ID of the voice channel you want to connect it to in the `defaultvoice` field in the `settings.json` file.

You should now be done! You can run mangobyte by calling `python3.5 mangobyte.py`, and you should probably set up a virtual environment so that nothing bad has a chance of happening.