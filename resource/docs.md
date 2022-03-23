<!-- Note that this file is consumed and used by the /docs command. Each h1 heading here is a separate docs command entry -->
<!-- Note that parts of this file are auto-generated, which is why theres some html comment placeholders below -->
# Argument: Match Filter

Mangobyte has a feature to allow users to be very specific when requesting information about dota matches. This allows users to filter for matches that are exactly what they are looking for. See filter options below.

__Filter options:__

*Note: Many of these options allow for slight variations on the text. If you want more info and can read regular expressions, see the MatchFilter class in [this file](https://github.com/mdiller/MangoByte/blob/master/cogs/utils/commandargs.py)*

- won/lost
- ranked/unranked
- turbo/ability draft/all draft
- radiant/dire
- solo/in a group
- significant/not-significant (*turbo matches, etc.*)
- mid/safe/off/roaming (*lane*)
- 5 days/2 weeks/1 year
- limit/count `<number>` (*number of matches*)
- with `<player>` (*they were in the match, not necessarily on your team*)
- without `<player>`
- as `<hero>`
- against/vs `<hero>`
- with `<hero>`
- `<item>` (*the exact name of the item in your inventory at end of game*)
- since `<patch>` (*gets matches since that patch was released*)
- `<patch>` (*gets matches during this patch*)

You can also specify to get matches for someone other than yourself by just @mentioning them or adding their steam id to the query

__Compatible Commands:__
<!-- MATCH_FILTER_COMMANDS_START -->
`/firstmatch`
`/lm`
`/matchids`
`/playerstats`
`/recent`
`/twenty`
<!-- MATCH_FILTER_COMMANDS_END -->

__Examples:__
`/recent won as tinker in the last year`
`/lm grim safelane radiant`
`/recent ranked won this week`
`/lm offlane on dire as shaker`
`/recent @Player lost vs axe`
`/firstmatch turbo with a group`
`/playerstats radiance puck`
`/playerstats puck since 7.28`

# Argument: Match

For any commands that take the "match" argument, you have several options in terms of what to give the command. These commands are looking for you to specify a specific match, which you can do in three different ways:
**1.** Specify a match by ID directly
**2.** Say 'lm', 'lastmatch', or 'me' to get the last match that you played. (assumes you have a dota account linked via `/userconfig steam`)
**3.** Specify a dota player by @'ing someone on discord with a mangobyte-linked dota account, or by giving their steam id.

Note that this uses "Match Filter" behind the hood for parsing a dota player, so you can also do some of the advanced things that you can do with that filter here.

__Compatible Commands:__
<!-- MATCH_ARGUMENT_COMMANDS_START -->
`/dotagif`
`/match graph`
`/match info`
`/match laning`
`/match skillbuild`
`/match story`
<!-- MATCH_ARGUMENT_COMMANDS_END -->

__Examples:__
`/match info 6481413969`
`/match graph lm`
`/match skillbuild @SomeoneOnDiscord`

# Slash Commands

Slash commands are here! This covers some frequently asked questions about slash commands

__Why?__
Discord has decided to change their rules and **bots are no longer going to be allowed to use prefix-based commands**. This only applies to bots in 75 or more servers, but mangobyte is in 8k+ at the time of me writing this. If you want to read more about this decision, head over to [thier blog post](https://support-dev.discord.com/hc/en-us/articles/4404772028055) where they announced this.

__"This sucks!"__
Yeah I know. There are definetly a lot of things about slash commands that are a downgrade form prefix-based commands. Things like not being able to easily see the arguments given to a command by someone else, not being able to copy-paste arguments, and things like having to juggle multiple bots that all want to share the same command name. The whole discord bot community is in agreement that this move by discord is frustrating, limiting, and doesn't support a healthy ecosystem. Unfortunatley this is just how it is and we have to deal with it.

__What about the TTS channel?__
The tts channel I've implemented for mangobyte is a really commonly used feature. Anyone who read the blog post from discord probably realized that not having access to messages will break the feature, so I'll have to apply for a "Message Content Intent". I plan on doing this, but need to get a couple things straight and setup before I apply to give us the best chance at getting it approved.

__Slash Commands aren't working on my server!__
A lot of people have been reporting issues with slash commands not working on thier server, or just not working for them at all. I've written a document with all the things I've learned helping people to get slash commands working for them. Feel free to check it out if you have issues.
[Slash Command Common Issues](https://github.com/mdiller/MangoByte/blob/master/docs/slash_command_common_issues.md)

__Migration Status__
Note that as of now, not all commands have been migrated over to slash commands. All will eventually be moved, but I'm doing it in chunks, so don't be surprised if you see some prefix commands and some slash commands for now.

**Current Migration Progress:** <!-- SLASH_PROGRESS_PERCENT_START -->45%<!-- SLASH_PROGRESS_PERCENT_END -->

# Slash Command Issues

A lot of people have been reporting issues with slash commands not working on thier server, or just not working for them at all. I've written a document with all the things I've learned helping people to get slash commands working for them. Feel free to check it out if you have issues.
[Slash Command Common Issues](https://github.com/mdiller/MangoByte/blob/master/docs/slash_command_common_issues.md)