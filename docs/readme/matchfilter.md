# Match Filter

The match filter is a natural language query system that lets you filter Dota 2 match history when using MangoByte commands. Filters are composed by combining keywords and values in any order.

**Endpoint:** `GET https://api.opendota.com/api/players/{account_id}/matches`

## Filter Options

| Keyword(s) | API Parameter | Type | Description |
|---|---|---|---|
| `won` / `lost` | `win` | post-filter | Won or lost the match |
| `ranked` / `unranked` | `lobby_type` | `7` / `0` | Ranked or unranked matchmaking |
| `significant` / `not-significant` | `significant` | `1` / `0` | Standard (AP/RD) or non-standard (turbo, etc.) modes |
| `turbo`, `ability draft`, `all draft`, etc. | `game_mode` | integer | Specific game mode (sets significant=0 automatically) |
| `radiant` / `dire` | `is_radiant` | post-filter | Which team you played on |
| `solo` | `party_size` | `1` | Solo queue only |
| `party` / `with a group` | _(post-filter)_ | — | Played with a party (party_size > 1) |
| `safelane` / `mid` / `offlane` / `jungle` | `lane_role` | post-filter | Lane role (requires parsed match) |
| `roaming` / `ganking` | _(post-filter)_ | — | Roaming role (requires parsed match) |
| `parsed` | _(post-filter)_ | — | Only matches with parsed data available |
| `5 days` / `2 weeks` / `1 year` | `date` | integer (days) | Matches within this time window |
| `since 7.35` / `7.35` | `date` | patch → days | Matches since (or during) that patch |
| `us west`, `us east`, `eu west`, etc. | `region` | integer | Server region |
| `as <hero>` | `hero_id` | integer | Hero you played |
| `against <hero>` / `vs <hero>` | `against_hero_id` | integer | Enemy hero |
| `with <hero>` / `alongside <hero>` | `with_hero_id` | post-filter | Ally hero |
| `with <player>` | `included_account_id` | integer | Player was in the match |
| `without <player>` | `excluded_account_id` | integer | Player was not in the match |
| `<item>` | _(post-filter)_ | — | Had this item in inventory at match end |
| `limit <n>` / `count <n>` / `show <n>` | `limit` | integer | Number of matches to return |
| `skip <n>` / `offset <n>` | `offset` | integer | Skip this many matches |
| `<@mention>` or `<steam_id>` | _(player target)_ | — | Get matches for another user |

### Post-filter vs Query Parameter

Most filters map directly to OpenDota query parameters. A few are **post-filters** — they fetch all matches first, then filter client-side. Post-filters require additional `project=` fields to be requested:

| Post-filter field | Required projection |
|---|---|
| `win`, `is_radiant` | `radiant_win`, `player_slot` |
| `lane_role`, `roaming` | `lane`, `is_roaming` |
| `with <hero>` | `hero_id` |
| `<item>` | inventory slot fields |
| `parsed` | `version` |

When post-filters are active, `limit` and `offset` are applied locally after filtering rather than sent to the API.

## Example API URLs

### Basic filters
```
/players/87287966/matches?win=1
/players/87287966/matches?lobby_type=7
/players/87287966/matches?game_mode=23&significant=0
```

### Hero filters
```
/players/87287966/matches?hero_id=75
/players/87287966/matches?against_hero_id=86
/players/87287966/matches?hero_id=75&win=1&lobby_type=7
```

### Time filters
```
/players/87287966/matches?date=7
/players/87287966/matches?date=30
/players/87287966/matches?date=365
```

### With projections (post-filter)
```
/players/87287966/matches?project=radiant_win&project=player_slot
/players/87287966/matches?project=lane&project=is_roaming
/players/87287966/matches?hero_id=75&project=radiant_win&project=player_slot
```

### Combined filters
```
/players/87287966/matches?hero_id=75&win=1&lobby_type=7&date=90
/players/87287966/matches?hero_id=11&game_mode=23&significant=0
/players/87287966/matches?included_account_id=194959475&hero_id=75
/players/87287966/matches?against_hero_id=1&lobby_type=7&date=30&limit=20
/players/87287966/matches?hero_id=75&with_hero_id=11&lobby_type=7
/players/87287966/matches?region=1&hero_id=75&win=1&date=180
/players/87287966/matches?lobby_type=7&party_size=1&hero_id=75&date=365
/players/87287966/matches?hero_id=75&limit=50&offset=50
```

## Match Filter in MangoByte

The match filter is accepted as a natural language string by commands like `/recent`, `/lm`, `/playerstats`, `/twenty`, etc.

### MangoByte Examples

```
/recent won as tinker in the last year
/lm grim safelane radiant
/recent ranked won this week
/lm offlane on dire as shaker
/recent @Player lost vs axe
/firstmatch turbo with a group
/playerstats radiance puck
/playerstats puck since 7.28
/recent us west solo ranked tinker won 2 weeks
/twenty ranked mid invoker won
/matchids sorted offlane earthshaker ranked
/recent with @Teammate as lion lost
/playerstats ranked offlane won since 7.35
```

## Game Mode IDs

| ID | Name |
|---|---|
| 1 | All Pick |
| 2 | Captains Mode |
| 3 | Random Draft |
| 4 | Single Draft |
| 5 | All Random |
| 16 | Captains Draft |
| 22 | Ranked All Pick |
| 23 | Turbo |
| 18 | Ability Draft |

## Region IDs

| ID | Region |
|---|---|
| 1 | US West |
| 2 | US East |
| 3 | Europe |
| 5 | SE Asia |
| 6 | Dubai |
| 7 | Australia |
| 8 | Stockholm |
| 9 | Austria |
| 10 | Brazil |
| 11 | South Africa |
| 12 | China (PW) |
| 13 | China |
