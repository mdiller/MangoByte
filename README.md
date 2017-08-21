# MangoByte<img align="right" src="/resource/images/readme/mangobyte.png"/>
A discord bot that provides the ability to play audio clips, play dota responses, answer questions, randomly react to messages, and a few other cool things. I'm using the [discord.py](https://github.com/Rapptz/discord.py) python wrapper for the [Discord API](https://discordapp.com/developers). I'm also making use of [dotabase](https://github.com/mdiller/dotabase), which is an open source repository (created by yours truly) containing data about the game [Dota 2](http://www.dota2.com).

You can invite mangobyte to your server via this [Invite Link](https://discordapp.com/oauth2/authorize?permissions=60480&scope=bot&client_id=213476188037971968), or you can try it out on my [Help Server](https://discord.gg/d6WWHxx).

## Commands
The following is a list of the commands that mangobyte has to offer

![Commands List](/resource/images/readme/help_all.png)

Example of `?lastgame` command:

![Lastgame Command](/resource/images/readme/lastgame.gif)

## Installation

I would recommend simply inviting mangobyte to your server via the [Invite Link](https://discordapp.com/oauth2/authorize?permissions=60480&scope=bot&client_id=213476188037971968), but if you want to contribute to mangobyte or just like running things, the following is how you can install and run your own instance of mangobyte.

Before installing and running your own instance of mangobyte, you will first need to install the following:

* Python 3.6
* Pip
* [dotabase](https://github.com/mdiller/dotabase)
* The rewrite version of [discord.py](https://github.com/Rapptz/discord.py):
	`python3.6 -m pip install -U git+https://github.com/Rapptz/discord.py@rewrite#egg=discord.py[voice]`

Now make sure to run `python3.6 -m pip install -r requirements.txt` to install the rest of the needed packages.

If you run `python3.6 mangobyte.py`, you will probably get an error message because the bot token isn't set. You'll have to [create a bot account](https://twentysix26.github.io/Red-Docs/red_guide_bot_accounts/) through discord in order to get one of these tokens. Note that the above link is for a different discord bot, and so the "Logging in with a token" section does not apply here. Now that you have a bot account, set the `token` field in the `settings.json` file to your new bot's token. After you have done this, and have invited your bot to your server, don't forget to add the ID of the voice channel you want to connect it to in the `defaultvoice` field in the `settings.json` file.

You should now be done! You can run mangobyte by calling `python3.6 mangobyte.py`, and you should probably set up a virtual environment so that nothing bad has a chance of happening.

### Example settings.json file

```json
{
	"token": "<token here>",
	"ttslang": "en-au",
	"error_logging": false,
	"debug": false
}
```