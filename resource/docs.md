
# Match Filter

I've recently added a feature to mangobyte to allow users to be very specific when requesting information about dota matches. This allows users to filter for matches that are exactly what they are looking for. See filter options below.

__So far this works on the following commands:__
`?matches`
`?lastmatch`
`?playerstats`

I'll probably add it to more commands once I get the implementation a little more fleshed out.

__Filter options:__
*Note: Many of these options allow for slight variations on the text. If you want more info and can read regular expressions, see the MatchFilter class in [this file](https://github.com/mdiller/MangoByte/blob/master/cogs/utils/commandargs.py)*

- won/lost
- ranked/unranked
- radiant/dire
- significant/not-significant (*turbo matches, etc.*)
- mid/safe/off/roaming (*lane*)
- 5 days/2 weeks/1 year
- limit/count `<number>` (*number of matches*)
- with `<player>` (*they were in the match, not necessarily on your team*)
- without `<player>`
- as `<hero>`
- against/vs `<hero>`
- with `<hero>`

You can also specify to get matches for someone other than yourself by just @mentioning them or adding their steam id to the query

__Examples:__
`?matches won as tinker in the last year`
`?lastmatch grim safelane radiant`
`?matches ranked won this week`
`?lastmatch offlane on dire as shaker`
`?matches @Player lost vs axe`
