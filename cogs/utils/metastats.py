from __main__ import settings, botdata, httpgetter
from cogs.utils.commandargs import HeroStatsTableArgs
import aiohttp
import asyncio
import async_timeout
import sys
import subprocess
import os
import numpy
import math
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from .tabledraw import (
    Table,
    ImageCell,
    TextCell,
    ColorCell,
    DoubleCell,
    SlantedTextCell,
    get_table_font,
)
from io import BytesIO
from .helpers import (
    run_command,
    get_pretty_time,
    read_json,
    UserError,
    format_duration_simple,
)
from .imagetools import *
from concurrent.futures import ThreadPoolExecutor


def get_hero_winrate(hero):
    """returns hero winrate from list of meta heroes"""
    if hero['pro_pick'] == 0: return 0
    else: return hero.get('pro_win', 0) / hero.get('pro_pick', 1)


def get_hero_pick_percent(hero, heroes):
    return hero.get('pro_pick', 0) / get_total_pro_games(heroes)


def get_hero_ban_percent(hero, heroes):
    return hero.get('pro_ban', 0) / get_total_pro_games(heroes)


def get_total_pro_games(heroes):
    total = 0
    for hero in heroes:
        total += hero.get('pro_pick', 0)  # sums total games in the list
    total = total/10
    print(total)
    return total

def get_hero_pickban_percent(hero, heroes):
    return (
        hero.get('pro_pick', 0) + hero.get('pro_ban', 0)
    ) / get_total_pro_games(heroes)
