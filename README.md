# MangoByte<img align="right" src="mangobyte.png"/>
A discord bot that provides the ability to play audio clips, play dota responses, answer questions, randomly react to messages, and a few other cool things. I'm using the [discord.py](https://github.com/Rapptz/discord.py) python wrapper for the [Discord API](https://discordapp.com/developers). I'm also making use of [dotabase](https://github.com/mdiller/dotabase), which is an open source repository (created by yours truly) containing data about the game [Dota 2](http://www.dota2.com).

## Commands
The following is a list of most of the commands that mangobyte has to offer

|        Command|Description |
| --------------|--- |
| ask           | Answers any question you might have |
| tts           | Like echo but for people who can't read |
| later         | Tells you how much later it is |
| playurl       | Plays an mp3 file at a url |
| setintro      | Sets your intro clip |
| replay        | Replays the last played clip |
| playlist      | Lists the audio clips available for the play command |
| clipinfo      | Gets information and a file for the given clip |
| play          | Plays an audio clip |
| setoutro      | Sets your outro clip |
| stop          | Stops the currently playing audio |
| opendotasql   | Submits an sql query to the opendota database |
| opendota      | Queries the opendota api |
| matchstory    | Tells the story of the match from the given perspective |
| lastmatchstory| Tells the story of the player's last match |
| profile       | Displays information about the player's dota profile |
| setsteam      | Links a discord user to their steam/dota account |
| match         | Gets a summary of the dota match with the given id |
| lastmatch     | Gets info about the player's last dota game |
| dota          | Plays a dota response |
| yes           | Oooooh ya. |
| no            | Nopes. |
| thanks        | Gives thanks |
| lol           | WOW I WONDER WAT THIS DOES |
| inthebag      | Proclaims that 'IT' (whatever it is) is in the bag |
| hello         | Says hello |
| lasagna       | A baked Italian dish |
| info          | Prints info about mangobyte |
| echo          | Echo... |
| ping          | Pings a number of times(within reason) |
| changelog     | Gets a rough changelog for mangobyte |
| help          | Shows this message. |

## Installation

Before installing and running your own instance of mangobyte, you will first need to install the following:

* Python 3.6
* Pip
* [dotabase](https://github.com/mdiller/dotabase)
* [discord.py](https://github.com/Rapptz/discord.py)

Now make sure to run `python3.5 -m pip install -r requirements.txt` to install the rest of the needed packages.

If you run `python3.5 mangobyte.py`, you will probably get an error message because the bot token isn't set. You'll have to [create a bot account](https://twentysix26.github.io/Red-Docs/red_guide_bot_accounts/) through discord in order to get one of these tokens. Note that the above link is for a different discord bot, and so the "Logging in with a token" section does not apply here. Now that you have a bot account, set the `token` field in the `settings.json` file to your new bot's token. After you have done this, and have invited your bot to your server, don't forget to add the ID of the voice channel you want to connect it to in the `defaultvoice` field in the `settings.json` file.

You should now be done! You can run mangobyte by calling `python3.5 mangobyte.py`, and you should probably set up a virtual environment so that nothing bad has a chance of happening.

### Example settings.json file

```json
{
	"token": "<token here>",
	"resourcedir": "resource/",
	"ttslang": "en-au"
}
```