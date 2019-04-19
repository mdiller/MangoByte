
# Match Filter

I've recently added a feature to mangobyte to allow users to be very specific when requesting information about dota matches. This allows users to filter for matches that are exactly what they are looking for. See filter options below.

__So far this works on the following commands:__
`?matches`
`?lastmatch`

I'll probably add it to more commands once I get the implementation a little more fleshed out.

__Filter options:__
*Note: Many of these options allow for slight variations on the text. If you want more info and can read regular expressions, see the MatchFilter class in [this file](https://github.com/mdiller/MangoByte/blob/master/cogs/utils/commandargs.py)*

- won/lost
- ranked/unranked
- radiant/dire
- significant/not-significant (turbo matches, etc.)
- mid/safe/off/roaming (lane)
- 5 days/2 weeks/1 year
- as <hero>
- against/vs <hero>
- with <hero>

The order you give these options in doesn't matter, and for the most part it should be able to figure out what you mean. I'm also planning on adding support for "with <player>" and "against <player>", I just haven't gotten around to it yet.

__Examples:__
`?matches won as tinker in the last year`
`?lastmatch grim safelane radiant`
`?matches ranked won this week`
`?lastmatch offlane on dire as shaker`
`?matches lost vs axe`
