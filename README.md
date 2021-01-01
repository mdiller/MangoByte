<h1 align="center">MangoByte</h1>

<p align="center">
	<a href="https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot&client_id=213476188037971968">
		<img alt="Servers" src="https://img.shields.io/badge/dynamic/json.svg?style=for-the-badge&label=servers&url=http%3A%2F%2Fdillerm.io%2Fdata%2Fmangobyte%2Fshieldstats.json&query=%24.servers&colorB=#4c1">
	</a>
	<a href="https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot&client_id=213476188037971968">
		<img alt="Registered Users" src="https://img.shields.io/badge/dynamic/json.svg?style=for-the-badge&label=registered%20users&url=http%3A%2F%2Fdillerm.io%2Fdata%2Fmangobyte%2Fshieldstats.json&query=%24.registered_users&colorB=#4c1">
	</a>
	<br>
	<a href="https://discord.gg/d6WWHxx">
		<img alt="Discord Help Server" src="https://discordapp.com/api/guilds/296486417197170688/embed.png?style=banner2">
	</a>
</p>

Mangobyte is a discord bot primarily focused on providing information about the game Dota 2, and doing text-to-speech in a voice channel. The text-to-speech has many different forms, including playing clips, playing voice lines from dota, and doing tts from user input. The Dota 2 information is both information about the players and their recent matches, as well as information extracted from the game itself about the stats of various heroes. It can also play an intro for users when they join the voice channel it is in. It is highly configurable, allowing server/guild owners to configure various options for their servers, as well as users to configure various options for themselves. I'm using the [discord.py](https://github.com/Rapptz/discord.py) python wrapper for the [Discord API](https://discordapp.com/developers). I'm also making use of [dotabase](https://github.com/mdiller/dotabase), which is an open source repository (created by yours truly) containing data about the game [Dota 2](http://www.dota2.com).

## Inviting Mangobyte

Want to try out mangobyte on your server? [Click Here](https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot&client_id=213476188037971968)

## Commands

<!-- COMMANDS_START -->
Mangobyte currently has 86 commands, separated into 7 categories

#### General
Commands that don't really fit into the other categories

```
?ask             | Answers any question you might have 
?blog            | Pulls up the most recent Dota blog post                       
?botstats        | Displays some bot statistics                                
?cat             | Gets a picture of my cat                                   
?changelog       | Gets a rough changelog for mangobyte                       
?choose          | Randomly chooses one of the given options                  
?docs            | Shows the documentation for the given topic                
?dog             | Gets a picture of one of my dogs                           
?donate          | Posts the donation information                             
?echo            | Echo...                                                    
?help            | Shows this message                                         
?info            | Prints info about mangobyte                                
?insult          | Gets a nice insult for ya                                  
?invite          | Prints the invite link                                     
?lasagna         | A baked Italian dish                                       
?ping            | Pongs a number of times(within reason)                     
?random_number   | Gets a random number between the minimum and maximum       
?reddit          | Displays a formatted reddit post                           
?restget         | Gets a json response from a rest api and returns it        
?scramble        | Scrambles the insides of words                             
?showerthought   | Gets a top post from r/ShowerThoughts                      
?userconfig      | Configures the bot's user-specific settings                
?wiki            | Looks up a thing on wikipedia                              
```

#### Audio
For playing audio in a voice channel

```
?clipinfo        | Gets information and a file for the given clip             
?clips           | Lists the local audio clips available for the play command 
?later           | Tells you how much later it is                             
?play            | Plays an audio clip                                        
?playurl         | Plays an mp3 file at a url                                 
?replay          | Replays the last played clip                               
?smarttts        | Automatically find the best fit for the tts given          
?stop            | Stops the currently playing audio                          
?tts             | Like echo but for people who can't read                    
?ttsclip         | Tries to text-to-speech the given clip                     
```

#### Dotabase
For information about Dota 2, and playing hero responses

```
?abilities       | Shows all of the abilities/spells for that hero            
?ability         | Gets information about a specific hero ability             
?addemoticon     | Adds a dota emoticon as an animated emoji                  
?aghanim         | Gets the aghs upgrade for the given hero or ability        
?chatwheel       | Plays the given chat wheel sound                           
?courage         | Generates a challenge build                                
?dota            | Plays a dota response                                      
?emoticon        | Gets the gif of a dota emoticon                            
?fuseheroes      | See what would happen if you fused two heroes together     
?hello           | Says hello                                                 
?hero            | Gets information about a specific hero                     
?herotable       | Displays a sorted table of heroes and their stats          
?inthebag        | Proclaims that 'IT' (whatever it is) is in the bag         
?item            | Gets information about a specific item                     
?leveledstats    | Gets the stats for a hero at the specified level           
?lol             | WOW I WONDER WAT THIS DOES                                 
?lore            | Gets the lore of a hero, ability, or item                  
?neutralitems    | Displays all of the neutral items                          
?no              | Nopes.                                                     
?recipe          | Shows the recipes involving this item                      
?talents         | Gets the talents of a specific hero                        
?thanks          | Gives thanks                                               
?yes             | Oooooh ya.                                                 
```

#### DotaStats
Commands for displaying information about Dota 2 players and matches

```
?dotagif         | Creates a gif of a specific part of a dota match           
?firstmatch      | Gets info about the player's first dota game               
?laning          | Creates gif of the laning stage with a caption             
?lastmatch       | Gets info about the player's last dota game                
?lastmatchstory  | Tells the story of the player's last match                 
?match           | Gets a summary of the dota match with the given id         
?matches         | Gets a list of your matches                                
?matchids        | Gets a list of matchids that match the given filter        
?matchstory      | Tells the story of the match                               
?opendota        | Queries the opendota api                                   
?parse           | Requests that OpenDota parses a match                      
?playerstats     | Gets player match statistics                               
?profile         | Displays information about the player's dota profile       
?rolesgraph      | Gets a graph displaying the player's hero roles            
?skillbuild      | Gets the ability upgrades for a match                      
?twenty          | Gets stats from the player's last 20 parsed games          
?whoishere       | Shows what discord users are which steam users             
```

#### Pokemon
Pokemon related commands

```
?pokecry         | Plays the pokemon's sound effect                           
?pokedex         | Looks up information about the indicated pokemon           
?shiny           | Gets the shiny version of this pokemon                     
```

#### Artifact
Artifact related commands

```
?card            | Displays info about the artifact card                      
?deck            | Displays the card list for the given deck                  
?updateartifact  | Updates all the artifact card data                         
```

#### Admin
Commands to help manage mangobyte on your server/guild

```
?botban          | Bans the user from using commands                          
?botunban        | Unbans the user, allowing them to use commands             
?config          | Configures the bot's settings for this server              
?disablecommand  | Disabled the specified command or command category         
?enablecommand   | Re-enables the specified command or command category       
?resummon        | Re-summons the bot to the voice channel                    
?summon          | Summons the bot to the voice channel                       
?unsummon        | Removes the bot from the voice channel                     
```

<!-- COMMANDS_END -->

## Examples

`?hero brew`

![hero_brew](/resource/images/readme/hero_brew.png)

`?ability black hole`

![ability_black_hole](/resource/images/readme/ability_black_hole.png)

`?item silver edge`

![item_silver_edge](/resource/images/readme/item_silver_edge.png)

`?herotable lvl 20 effective hp`

<img width="600px" src="/resource/images/readme/herotable_lvl20_effhp.png"/>

`?lastmatch`

![lastmatch](/resource/images/readme/lastmatch.png)

`?playerstats`

![playerstats](/resource/images/readme/playerstats.png)

`?laning`

![laning](/resource/images/readme/laning.gif)

`?recent`

<img width="600px" src="/resource/images/readme/recent.png"/>

`?recent tinker wins` (See the options you can use for this [here](resource/docs.md))

<img width="600px" src="/resource/images/readme/recent_tinker_wins.png"/>

`?rolesgraph`

![rolesgraph](/resource/images/readme/rolesgraph.png)

`?help config`

![help_config](/resource/images/readme/help_config.png)

`?help userconfig`

![help_userconfig](/resource/images/readme/help_userconfig.png)


## Installation

I would recommend simply inviting mangobyte to your server via the [Invite Link](https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot&client_id=213476188037971968), but if you want to contribute to mangobyte or just like running things, the following is how you can install and run your own instance of mangobyte.

Before installing and running your own instance of mangobyte, you will first need to install the following:

* Python 3.6
* Pip
* Dependencies: `python3.6 -m pip install -r requirements.txt`
* [ffmpeg](https://ffmpeg.org) (the tool used for playing audio)
* [gifsicle](https://www.lcdf.org/gifsicle/) (the tool used for creating gifs)

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
