
# Match Filter

I've recently added a feature to mangobyte to allow users to be very specific when requesting information about dota matches. This allows users to filter for matches that are exactly what they are looking for. See filter options below.

__So far this works on the following commands:__
`?matches`
`?matchids`
`?lastmatch`
`?firstmatch`
`?playerstats`

I'll probably add it to more commands once I get the implementation a little more fleshed out.

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

__Examples:__
`?matches won as tinker in the last year`
`?lastmatch grim safelane radiant`
`?matches ranked won this week`
`?lastmatch offlane on dire as shaker`
`?matches @Player lost vs axe`
`?firstmatch turbo with a group`
`?playerstats radiance puck`
`?playerstats puck since 7.28`

# Match Argument

For any commands that take the "match" argument, you have several options in terms of what to give the command. These commands are looking for you to specify a specific match, which you can do in three different ways:
**1.** Specify a match by ID directly
**2.** Say 'lm', 'lastmatch', or 'me' to get the last match that you played. (assumes you have a dota account linked via `/userconfig steam`)
**3.** Specify a dota player by @'ing someone on discord with a mangobyte-linked dota account, or by giving their steam id.

Note that this uses "Match Filter" behind the hood for parsing a dota player, so you can also do some of the advanced things that you can do with that filter here.

__Examples:__
`/match info 6481413969`
`/match graph lm`
`/match skillbuild @SomeoneOnDiscord`

# Slash Commands

If youre wondering if I'll be moving to slash commands, yes, that process is under way and all of the commands will eventually be moved. Like this one for example! Any commands that are still a prefix command will eventually be moved to a slash command.
