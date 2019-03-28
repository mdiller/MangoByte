# MangoByte<img align="right" src="/resource/images/readme/mangobyte.png"/>

[![Servers](https://img.shields.io/badge/dynamic/json.svg?label=servers&url=http%3A%2F%2Fdillerm.io%2Fshieldstats%2Fmangobyte.json&query=%24.servers&colorB=#4c1)](https://discordapp.com/oauth2/authorize?permissions=60480&scope=bot&client_id=213476188037971968)
[![Registered Users](https://img.shields.io/badge/dynamic/json.svg?label=registered%20users&url=http%3A%2F%2Fdillerm.io%2Fshieldstats%2Fmangobyte.json&query=%24.registered_users&colorB=#4c1)](https://discordapp.com/oauth2/authorize?permissions=60480&scope=bot&client_id=213476188037971968)

- [Add the bot to your server](https://discordapp.com/oauth2/authorize?permissions=60480&scope=bot&client_id=213476188037971968)
- [Join the MangoByte help server](https://discord.gg/d6WWHxx)

A discord bot that provides the ability to play audio clips, play dota responses, answer questions, randomly react to messages, and a large number of other actions. I'm using the [discord.py](https://github.com/Rapptz/discord.py) python wrapper for the [Discord API](https://discordapp.com/developers). I'm also making use of [dotabase](https://github.com/mdiller/dotabase), which is an open source repository (created by yours truly) containing data about the game [Dota 2](http://www.dota2.com).

## Examples

Example of a gif you can create with `?laning` or `?dotagif`:

![DotaGif Command](/resource/images/readme/dotagif.gif)

Example of `?lastgame` command:

![Lastgame Command](/resource/images/readme/lastgame.gif)

This is the long list of all of the commands. You can get this from `?help all`

![Commands List](/resource/images/readme/help_all.png)

## Installation

I would recommend simply inviting mangobyte to your server via the [Invite Link](https://discordapp.com/oauth2/authorize?permissions=60480&scope=bot&client_id=213476188037971968), but if you want to contribute to mangobyte or just like running things, the following is how you can install and run your own instance of mangobyte.

Before installing and running your own instance of mangobyte, you will first need to install the following:

* Python 3.6
* Pip
* Dependencies: `python3.6 -m pip install -r requirements.txt`
* The rewrite version of [discord.py](https://github.com/Rapptz/discord.py) with voice support: `python3.6 -m pip install -U git+https://github.com/Rapptz/discord.py@rewrite#egg=discord.py[voice]`
* [ffmpeg](https://ffmpeg.org) (the tool used for playing audio)

If you run `python3.6 mangobyte.py`, you will probably get an error message because the bot token isn't set. You'll have to [create a bot account](https://twentysix26.github.io/Red-Docs/red_guide_bot_accounts/) through discord in order to get one of these tokens. Note that the above link is for a different discord bot, and so the "Logging in with a token" section does not apply here. Now that you have a bot account, set the `token` field in the `settings.json` file to your new bot's token. After you have done this, and have invited your bot to your server, don't forget to add the ID of the voice channel you want to connect it to in the `defaultvoice` field in the `settings.json` file.

You should now be done! You can run mangobyte by calling `python3.6 mangobyte.py`, and you should probably set up a virtual environment so that nothing bad has a chance of happening.

### Example settings.json file

```json
{
	"token": "<token here>",
	"error_logging": false,
	"debug": false
}
```
For explanation of each option, see the comments on the properties in [settings.py](cogs/utils/settings.py)
