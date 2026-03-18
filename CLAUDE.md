# MangoByte — Claude Code Instructions

## Project Overview

MangoByte is a Discord bot built with Python and [disnake](https://github.com/DisnakeDev/disnake). It focuses on:
- Dota 2 information (heroes, abilities, items, match stats)
- Text-to-speech and audio clip playback in voice channels
- General/misc Discord utility commands

## Running the Bot

```bash
uv run python mangobyte.py
```

Dependencies are managed with **uv** (`pyproject.toml`). The `.venv` is auto-created on first run.

Config lives in `settings.json` at the repo root (gitignored — contains the bot token and API keys).

## Architecture

| Path | Purpose |
|---|---|
| `mangobyte.py` | Entry point, bot setup, event handlers |
| `main.py` | Alternative entry (check before modifying) |
| `cogs/` | Command cogs — one file per category |
| `utils/tools/` | Shared singletons: `settings`, `logger`, `botdata`, `httpgetter` |
| `utils/command/` | Command argument parsing, checks, pagination |
| `utils/drawing/` | Image generation (tables, graphs, dota visuals) |
| `utils/other/` | Error handling, initialization, misc helpers |
| `resource/` | Static assets (images, audio clips, JSON data) |
| `botdata.json` | Persistent bot data (user/guild configs) |
| `_scripts/` | One-off maintenance scripts |
| `_data/` | Misc data files and diffs |
| `docs/` | Documentation files |
| `deploy/` | Deployment config |

### Cogs

- `cogs/general.py` — General commands (`/help`, `/misc`, `/wiki`, `/reddit`, etc.)
- `cogs/audio.py` — Audio/TTS/clip commands
- `cogs/dotabase.py` — Dota 2 game data commands (uses `dotabase` package)
- `cogs/dotastats.py` — Dota 2 player/match stat commands (OpenDota + Stratz APIs)
- `cogs/admin.py` — Server config and bot management
- `cogs/owner.py` — Owner-only commands
- `cogs/pokemon.py` — Pokemon commands

### Global Singletons (import from `utils.tools.globals`)

```python
from utils.tools.globals import botdata, logger, settings, httpgetter
```

- `settings` — Reads `settings.json`
- `botdata` — Persistent storage wrapper around `botdata.json`
- `httpgetter` — Async HTTP client
- `logger` — Logging wrapper (optionally ships to Loki)

## Key External Dependencies

- **disnake** — Discord API wrapper (slash commands via `disnake.ext.commands`)
- **dotabase** — Local Dota 2 game data (SQLite, maintained separately at `c:\dev\projects\dotabase`)
- **gTTS** — Google Text-to-Speech
- **Pillow** — Image generation
- **ffmpeg** — Audio playback (system dependency, must be installed separately)
- **gifsicle** — GIF creation (system dependency)
- OpenDota API + Stratz API for match data

## settings.json Keys

- `token` — Discord bot token (required)
- `debug` — Enable debug mode
- `odota` — OpenDota API token
- `stratz` — Stratz API token (required for `/match laning`)
- `reddit` — Reddit API credentials
- `loki` — Loki logging config
- `shard_count` — Manual shard count override
- `infodump_path` — Path to dump bot info JSON

## Commands Update Script

To regenerate the README command list and other static files:

```bash
uv run python mangobyte.py commands
```

## Notes

- All slash commands use disnake's application command system
- `cogs/mangocog.py` is the base class for cogs
- The bot runs as an `AutoShardedBot`
- `botdata.json` stores per-user and per-guild config — don't hand-edit unless necessary
