from __main__ import settings, botdata, httpgetter
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
from .tabledraw import Table, ImageCell, TextCell, ColorCell, DoubleCell, SlantedTextCell
from io import BytesIO
from .helpers import run_command, get_pretty_time, read_json, UserError, format_duration_simple
from .imagetools import *
from concurrent.futures import ThreadPoolExecutor

radiant_icon = settings.resource("images/radiant.png")
dire_icon = settings.resource("images/dire.png")

trim_color = "#2C2F33"
background_color = "#23272A"

hero_infos = {}
item_infos = {}

def init_dota_info(hero_info, item_info):
	global hero_infos, item_infos
	hero_infos = hero_info
	item_infos = item_info

def get_hero_name(hero_id):
	return hero_infos[hero_id]["name"]

async def get_url_image(url):
	return Image.open(await httpgetter.get(url, "bytes", cache=True))

async def get_hero_image(hero_id):
	try:
		return await get_url_image(hero_infos[hero_id]["image"])
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_hero_icon(hero_id):
	try:
		return await get_url_image(hero_infos[hero_id]["icon"])
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_hero_portrait(hero_id):
	try:
		return await get_url_image(hero_infos[hero_id]["portrait"])
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_item_image(item_id):
	try:
		return await get_url_image(item_infos[item_id]["icon"])
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_neutral_image(item):
	background = Image.new("RGBA", (64, 64))
	size = background.size
	circle_diameter = 48
	circle_thickness = 4
	img_scale = circle_diameter / 64

	inner_radius = circle_diameter / 2
	inner_circle = ((size[0] / 2) - inner_radius, (size[1] / 2) - inner_radius, 
					(size[0] / 2) + inner_radius, (size[1] / 2) + inner_radius)
	outer_radius = inner_radius + circle_thickness
	outer_circle = ((size[0] / 2) - outer_radius, (size[1] / 2) - outer_radius, 
					(size[0] / 2) + outer_radius, (size[1] / 2) + outer_radius)
	if item:
		draw = ImageDraw.Draw(background)
		draw.ellipse(outer_circle, fill="#393939")
		
		item_img = await get_item_image(item)
		item_img = item_img.resize((int(item_img.size[0] * img_scale), int(item_img.size[1] * img_scale)))
		item_img = item_img.crop((
			math.floor((item_img.size[0] - background.size[0]) / 2),
			math.floor((item_img.size[1] - background.size[1]) / 2),
			item_img.size[0] - math.ceil((item_img.size[0] - background.size[0]) / 2),
			item_img.size[1] - math.ceil((item_img.size[1] - background.size[1]) / 2))
		)
		mask_circle = Image.new("RGBA", background.size)
		mask_draw = ImageDraw.Draw(mask_circle)
		mask_draw.ellipse(inner_circle, fill="#ffffff")
		temp_image = Image.new("RGBA", (64, 64))
		temp_image.paste(item_img, (0, 0), mask=mask_circle)
		
		return Image.alpha_composite(background, temp_image)
	else:
		return background


async def get_item_images(player):
	images = []
	item_size = (88, 64)
	for i in range(0, 6):
		item = player.get(f"item_{i}")
		if item:
			images.append(await get_item_image(item))
		else:
			images.append(Image.new("RGBA", item_size))
	item = player.get("item_neutral")
	if item:
		images.append(await get_neutral_image(item))


	widths, heights = zip(*(i.size if i else item_size for i in images))
	result = Image.new("RGBA", (sum(widths), max(heights)))

	x = 0
	for i in range(len(images)):
		result.paste(images[i], (x, 0))
		x += item_size[0]
	return result


def get_lane(player):
	lane_dict = { 1: "Bot", 3: "Top", None: "" }
	lane_role_dict = { 1: "Safe", 2: "Mid", 3: "Off", 4: "Jungle", None: "" }
	if 'is_roaming' in player and player['is_roaming']:
		return "Roaming"
	elif player.get('lane') in lane_dict:
		return f"{lane_role_dict[player.get('lane_role')]}({lane_dict[player.get('lane')]})"
	else:
		return lane_role_dict[player.get('lane_role')]


async def add_player_row(table, player, is_parsed):
	row = [
		ColorCell(width=5, color=("green" if player["isRadiant"] else "red")),
		ImageCell(img=await get_hero_image(player["hero_id"]), height=48),
		TextCell(player.get("personaname", "Anonymous")),
		TextCell(player.get("kills")),
		TextCell(player.get("deaths")),
		TextCell(player.get("assists")),
		TextCell(player.get("gold_per_min"), color="yellow"),
		ImageCell(img=await get_item_images(player), height=48)
	]
	if is_parsed:
		row[-1:-1] = [
			TextCell(player.get("actions_per_min")),
			TextCell(get_lane(player)),
			TextCell(player.get("pings", "-"), horizontal_align="center")
		]
	table.add_row(row)

async def draw_match_table(match):
	is_parsed = match.get("version")
	table = Table(background=background_color)
	# Header
	headers = [
		TextCell("", padding=0),
		TextCell(""),
		TextCell(""),
		TextCell("K", horizontal_align="center"),
		TextCell("D", horizontal_align="center"),
		TextCell("A", horizontal_align="center"),
		TextCell("GPM", color="yellow"),
		TextCell("Items")
	]
	if is_parsed:
		headers[-1:-1] = [
			TextCell("APM"),
			TextCell("Lane"),
			TextCell("Pings")
		]
	table.add_row(headers)
	for cell in table.rows[0]:
		cell.background = trim_color

	# Do players
	for player in match["players"]:
		if player['isRadiant']:
			await add_player_row(table, player, is_parsed)
	table.add_row([ColorCell(color=trim_color, height=5) for i in range(len(headers))])
	for player in match["players"]:
		if not player['isRadiant']:
			await add_player_row(table, player, is_parsed)
	return table.render()

async def create_match_image(match):
	table_border = 10
	table_image = await draw_match_table(match)

	image = Image.new('RGBA', (table_image.size[0] + (table_border * 2), table_image.size[1] + table_border + 64))
	draw = ImageDraw.Draw(image)
	draw.rectangle([0, 0, image.size[0], image.size[1]], fill=background_color)
	draw.rectangle([0, 64, image.size[0], image.size[1]], fill=trim_color)
	image.paste(table_image, (table_border, 64))

	title = TextCell(f"{'Radiant' if match['radiant_win'] else 'Dire'} Victory", font_size=48, color=("green" if match['radiant_win'] else "red"))
	title.render(draw, image, 64, 0, image.size[0] - 64, 64)

	team_icon = Image.open(radiant_icon if match['radiant_win'] else dire_icon).resize((64, 64))
	temp_image = Image.new("RGBA", image.size)
	temp_image.paste(team_icon, (0, 0))
	image = Image.alpha_composite(image, temp_image)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp

async def combine_image_halves(img_url1, img_url2):
	img1 = Image.open(await httpgetter.get(img_url1, "bytes", cache=True)).convert("RGBA")
	img2 = Image.open(await httpgetter.get(img_url2, "bytes", cache=True)).convert("RGBA")

	pixels1 = img1.load()
	pixels2 = img2.load()

	width = img1.size[0]
	height = img1.size[1]

	for j in range(height):
		for i in range(abs(width - j), width):
			pixels1[i,j] = pixels2[i,j]

	fp = BytesIO()
	img1.save(fp, format="PNG")
	fp.seek(0)

	return fp

def optimize_gif(uri, filename):

	# if need further, try doing O3 only after colors instead of before
	optimization = [
		["--colors", "256"],
		["-O3"],
		["--colors", "128"],
		["-O3"],
	]
	size_limit = 8

	print(f"optimizing: {uri}")
	file_size = os.path.getsize(filename) / 1000000
	print(f"bytes: {file_size} MB")
	i = 0

	while file_size >= size_limit and i < len(optimization):
		output = run_command(["gifsicle", "--conserve-memory", filename, "-o", filename] + optimization[i])
		file_size = os.path.getsize(filename) / 1000000
		print(f"bytes: {file_size} MB")
		i += 1

	if file_size >= size_limit:
		raise ValueError(f"couldn't optimize {uri} far enough")

# places an icon on the map at the indicated x/y using the dota coordinant system
# scale is how much to scale the icon
def place_icon_on_map(map_image, icon, x, y):
	scale = map_image.width / 128
	x = (x - 64) * scale
	y = (128 - (y - 64)) * scale
	return paste_image(map_image, icon, int(x - (icon.width / 2)), int(y - (icon.height / 2)))

# wraps the main gif creation code so it doesnt block
async def create_dota_gif(bot, match, stratz_match, start_time, end_time, ms_per_second=100):
	uri = f"match_gif:{match['match_id']}:{start_time}:{end_time}:{ms_per_second}"

	filename = httpgetter.cache.get_filename(uri)
	if filename and not settings.debug:
		return filename
	filename = await httpgetter.cache.new(uri, "gif")

	hero_icons = {}

	for player in stratz_match["players"]:
		hero_id = player["heroId"]
		hero_icons[str(hero_id)] = await get_hero_icon(hero_id)

	return await bot.loop.run_in_executor(ThreadPoolExecutor(max_workers=1), create_dota_gif_main, match, stratz_match, start_time, end_time, ms_per_second, filename, uri, hero_icons)

# the main code for creating the dota gif. this should be run in a separate thread because it blocks
def create_dota_gif_main(match, stratz_match, start_time, end_time, ms_per_second, filename, uri, hero_icons):
	building_data = read_json(settings.resource("json/building_data.json"))

	map_image = Image.open(settings.resource("images/map/dota_map.png"))
	map_image = map_image.resize((256, 256), Image.ANTIALIAS)

	clock_bg_image = Image.open(settings.resource("images/map/clock_background.png"))
	font = ImageFont.truetype(settings.resource("images/arial_unicode_bold.ttf"), 16)

	reverse = end_time < start_time
	if reverse:
		temp = start_time
		start_time = end_time
		end_time = temp

	match_start = -89
	if start_time < match_start:
		start_time = match_start
	if end_time > match["duration"]:
		end_time = match["duration"]

	players = []
	for player in stratz_match["players"]:
		playbackData = player["playbackData"]
		positionEvents = playbackData["playerUpdatePositionEvents"]
		deathEvents = playbackData["deathEvents"]
		scale = 0.75
		icon = hero_icons[str(player["heroId"])]
		icon = icon.resize((int(icon.width * scale), int(icon.height * scale)), Image.ANTIALIAS)
		# icon = outline_image(icon, 2, (0, 255, 0) if player["isRadiant"] else (255, 0, 0))
		x = 0
		y = 0
		data = {
			"icon": icon
		}
		
		for t in range(match_start, end_time + 1):
			event = next((e for e in positionEvents if e["time"] == t), None)
			if event:
				x = event["x"]
				y = event["y"]
			if t >= start_time:
				data[t] = { "x": x, "y": y }

		death_timer = 0
		for t in range(match_start, end_time + 1):
			event = next((e for e in deathEvents if e["time"] == t), None)
			if event:
				death_timer = event["timeDead"]
			if t >= start_time:
				data[t]["dead"] = death_timer > 0
			if death_timer > 0:
				death_timer -= 1

		players.append(data)

	objectiveEvents = match["objectives"]
	buildings = []
	for b in building_data:
		icon = Image.open(settings.resource(f"images/map/{b['icon']}"))
		size = {
			"tower": int(map_image.width * (16 / 300)),
			"barracks": int(map_image.width * (12 / 300)),
			"ancient": int(map_image.width * (25 / 300))
		}[b["type"]]
		icon = icon.resize((size, size), Image.ANTIALIAS)

		building = {
			"icon": icon,
			"x": b["x"],
			"y": b["y"]
		}
		event = next((e for e in objectiveEvents if e.get("key") == b["key"]), None)
		if event:
			building["death"] = event["time"]
		buildings.append(building)

	#sort from top right to bottom left for drawing
	buildings = sorted(buildings, key=lambda b: b["x"] + b["y"], reverse=True)

	# runes
	runeEvents = stratz_match["playbackData"]["runeEvents"]
	current_runes = {}
	runes = {}
	for t in range(match_start, end_time + 1):
		events = filter(lambda e: e["time"] == t, runeEvents)
		for e in filter(lambda e: e["time"] == t and e["action"] == 0, runeEvents):
			current_runes[e["id"]] = {
				"type": e["runeType"],
				"x": e["x"],
				"y": e["y"]
			}
		if t >= start_time and current_runes:
			runes[t] = current_runes.copy()
		for e in filter(lambda e: e["time"] == t and e["action"] == 1, runeEvents):
			if e["id"] in current_runes:
				del current_runes[e["id"]]
	# rune icons
	rune_icons = {}
	for i in range(0, 9):
		scale = 0.5
		icon = Image.open(settings.resource(f"images/map/rune_{i}.png"))
		rune_icons[i] = icon.resize((int(icon.width * scale), int(icon.height * scale)), Image.ANTIALIAS)


	process = subprocess.Popen(["gifsicle", "--multifile", "-d", str(ms_per_second // 10), "--conserve-memory", "-O3", "-", "-o", filename], stdin=subprocess.PIPE, bufsize=-1)

	time_range = range(start_time, end_time + 1)

	if reverse:
		time_range = range(end_time, start_time - 1, -1)

	for t in time_range:
		image = map_image.copy()
		for building in buildings:
			if t < building.get("death", t + 1):
				image = place_icon_on_map(image, building["icon"], building["x"], building["y"])
		for player in players:
			icon = player["icon"].convert("LA") if player[t]["dead"] else player["icon"]
			image = place_icon_on_map(image, icon, player[t]["x"], player[t]["y"])
		for rune in runes.get(t, {}):
			rune = runes[t][rune]
			image = place_icon_on_map(image, rune_icons[rune["type"]], rune["x"], rune["y"])

		image = paste_image(image, clock_bg_image, (image.width // 2) - (clock_bg_image.width // 2), 0)
		draw = ImageDraw.Draw(image)
		clock_text = get_pretty_time(abs(t))
		clock_pos = ((image.width // 2) - (font.getsize(clock_text)[0] // 2), -1)		
		draw.text(clock_pos, clock_text, font=font, fill="#ffffff")

		image.save(process.stdin, "gif")
		image.close()

	process.stdin.close()
	process.wait()

	optimize_gif(uri, filename)

	return filename

async def create_dota_emoticon(emoticon, url):
	uri = f"dota_emoticon:{emoticon.name}"
	filename = httpgetter.cache.get_filename(uri)
	if filename and not settings.debug:
		return filename

	filename = await httpgetter.cache.new(uri, "gif")

	image = Image.open(await httpgetter.get(url, "bytes", cache=True))
	image = remove_semi_transparent(image, (255, 255, 255, 0))

	frame_width = image.width / emoticon.frames

	process = subprocess.Popen(["gifsicle", 
		"--multifile", 
		"-d", str(emoticon.ms_per_frame // 10), 
		"-U", "--disposal=bg",
		"--loopcount=0",
		"--transparent", "0",
		"-", "-o", filename], stdin=subprocess.PIPE, bufsize=-1)

	for i in range(0, emoticon.frames):
		box = (i * frame_width, 0, (i + 1) * frame_width, image.height)
		frame = image.crop(box)
		frame.save(process.stdin, "gif")

	process.stdin.close()
	process.wait()

	return filename


async def dota_rank_icon(rank_tier, leaderboard_rank):
	if rank_tier is None:
		rank_tier = 0

	uri = f"dota_rank:{rank_tier}_{leaderboard_rank}"
	print(uri)
	filename = httpgetter.cache.get_filename(uri)
	if filename and not settings.debug:
		return filename

	filename = await httpgetter.cache.new(uri, "png")

	badge_num = rank_tier // 10
	stars_num = min(rank_tier % 10, 7)
	modifier = ""

	if badge_num == 8 and leaderboard_rank:
		stars_num = 0
		if leaderboard_rank <= 10:
			modifier = "c"
		elif leaderboard_rank <= 100:
			modifier = "b"

	image = Image.open(settings.resource(f"images/ranks/rank_{badge_num}{modifier}.png"))

	if stars_num > 0:
		stars_image = Image.open(settings.resource(f"images/ranks/stars_{stars_num}.png"))
		image = paste_image(image, stars_image, 0, 0)


	if leaderboard_rank:
		draw = ImageDraw.Draw(image)

		box_width = 256
		box_height = 50

		cell = TextCell(leaderboard_rank, color="#feffe5", font_size=50, horizontal_align="center")
		cell.render(draw, image, 0, 232 - box_height, box_width, box_height)


	image.save(filename, "png")

	return filename

def get_datetime_cell(match, region_data):
	match_date = datetime.utcfromtimestamp(match["start_time"])
	region = str(match.get("region"))
	if region and region in region_data:
		match_date += timedelta(hours=region_data[region]["UTC_offset"])
	# character for leading space is different on windows
	lead_char = "#" if os.name == "nt" else "-"
	str_date = match_date.strftime(f"%b %{lead_char}d %Y")
	str_time = match_date.strftime(f"%{lead_char}I:%M %p")
	return DoubleCell(
		TextCell(str_date, font_size=18, horizontal_align="center"),
		TextCell(str_time, font_size=18, horizontal_align="center")
	)


async def draw_matches_table(matches, game_strings):
	region_data = read_json(settings.resource("json/region_data.json"))	

	border_size = 10
	grey_color = "#BBBBBB"
	table = Table(background=background_color)
	# Header
	headers = [
		TextCell("Hero", padding=0),
		TextCell(""),
		TextCell("Result"),
		TextCell("K", horizontal_align="center"),
		TextCell("D", horizontal_align="center"),
		TextCell("A", horizontal_align="center"),
		TextCell("Duration"),
		TextCell("Type"),
		TextCell("Date")
	]
	table.add_row(headers)
	for cell in table.rows[0]:
		cell.background = trim_color

	table.add_row([ColorCell(color=trim_color, height=6) for i in range(len(headers))])
	first = True
	for match in matches:
		won_match = bool(match["radiant_win"]) == bool(match["player_slot"] < 128)
		game_mode = game_strings.get(f"game_mode_{match['game_mode']}", "Unknown")
		lobby_type = game_strings.get(f"lobby_type_{match['lobby_type']}", "Unknown")
		if first:
			first = False
		else:
			table.add_row([ColorCell(color=background_color, height=12) for i in range(len(headers))])
		table.add_row([
			ImageCell(img=await get_hero_image(match["hero_id"]), height=48),
			DoubleCell(
				TextCell(get_hero_name(match["hero_id"]), font_size=24),
				TextCell(match.get("match_id"), font_size=12, horizontal_align="left", color=grey_color)
			),
			TextCell("Win" if won_match else "Loss", color=("green" if won_match else "red"), horizontal_align="center"),
			TextCell(match.get("kills")),
			TextCell(match.get("deaths")),
			TextCell(match.get("assists")),
			TextCell(format_duration_simple(match.get("duration")), horizontal_align="center"),
			DoubleCell(
				TextCell(game_mode, font_size=18, padding_right=15, color=grey_color),
				TextCell(lobby_type, font_size=18, padding_right=15, color=grey_color)
			),
			get_datetime_cell(match, region_data)
		])
	image = table.render()

	border_image = Image.new('RGBA', (image.size[0] + (border_size * 2), image.size[1] + border_size), color=trim_color)
	image = paste_image(border_image, image, border_size, 0)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp


# given talents as they are stored in dotabase
async def draw_hero_talents(hero):
	talents = hero.talents.split("|")
	talent_rows = [
		[ talents[7], talents[6] ],
		[ talents[5], talents[4] ],
		[ talents[3], talents[2] ],
		[ talents[1], talents[0] ]
	]

	image = Image.open(settings.resource("images/talents.png"))
	draw = ImageDraw.Draw(image)

	header_x = 19
	header_y = 17
	header_width = 655
	header_height = 51

	cell = TextCell(hero.localized_name, color="#dddddd", font_size=28, horizontal_align="center")
	cell.render(draw, image, header_x, header_y, header_width, header_height)

	box_width = 306
	box_height = 73
	box_margin_y = 14

	start_y = 70
	start_x_left = 14
	start_x_right = 370
	start_x = [ start_x_left, start_x_right ]

	for i in range(0, 4):
		for j in range(0, 2):
			x = start_x[j]
			y = start_y + (i * (box_height + box_margin_y))
			text = talent_rows[i][j]

			cell = TextCell(text, color="#cca770", font_size=20, wrap=True, padding=[ 0, 15, 0, 15 ], horizontal_align="center")
			cell.render(draw, image, x, y, box_width, box_height)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp

async def fuse_hero_images(hero1, hero2):
	file1 = await httpgetter.get(hero_infos[hero1.id]["image"], "filename", cache=True)
	file2 = await httpgetter.get(hero_infos[hero2.id]["image"], "filename", cache=True)

	fp = BytesIO()
	colorize_image(file1, file2, fp)
	fp.seek(0)

	return fp

async def draw_courage(hero_id, icon_ids):
	# scaled to 128 height
	hero_image = await get_hero_portrait(hero_id)
	hero_image = hero_image.resize((97, 128), Image.ANTIALIAS)

	table = Table()
	table.add_row([
		ColorCell(color="white", width=97, height=64),
		ImageCell(img=await get_item_image(icon_ids[0])),
		ImageCell(img=await get_item_image(icon_ids[1])),
		ImageCell(img=await get_item_image(icon_ids[2]))
	])
	table.add_row([
		ColorCell(color="white", width=97, height=64),
		ImageCell(img=await get_item_image(icon_ids[3])),
		ImageCell(img=await get_item_image(icon_ids[4])),
		ImageCell(img=await get_item_image(icon_ids[5]))
	])
	image = table.render()
	image = paste_image(image, hero_image, 0, 0)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp

async def draw_artifact_deck(deck_string, cards, hero_turns, card_counts):
	uri = f"artifact_deck:{deck_string}"
	filename = httpgetter.cache.get_filename(uri)
	if filename and not settings.debug:
		return filename

	filename = await httpgetter.cache.new(uri, "png")

	sorting_info = [
		{
			"filter": lambda c: c.type == "Hero",
			"sort": lambda c: hero_turns[c.id]
		},
		{
			"filter": lambda c: c.type != "Hero" and c.type != "Item",
			"sort": lambda c: c.mana_cost
		},
		{
			"filter": lambda c: c.type == "Item",
			"sort": lambda c: c.gold_cost
		}
	]
	ordered_cards = []
	for info in sorting_info:
		for card in sorted(filter(info["filter"], cards), key=info["sort"]):
			ordered_cards.append(card)

	column_count = 5
	border_size = 10
	grey_color = "#BBBBBB"
	table = Table(background=background_color)

	table.add_row([ColorCell(color=trim_color, height=border_size) for i in range(column_count)])
	first = True
	for card in ordered_cards:
		cost = ""
		if card.type != "Hero":
			if card.type == "Item":
				cost = card.gold_cost
			else:
				cost = card.mana_cost
		last_cell = ""
		if card.type == "Hero":
			last_cell = f"Turn {hero_turns.get(card.id)}"
		else:
			last_cell = f"x {card_counts.get(card.id)}"
		if first:
			first = False
		else:
			table.add_row([ColorCell(color=background_color, height=2) for i in range(column_count)])
		table.add_row([
			ImageCell(img=await get_url_image(card.mini_image), height=48),
			ImageCell(img=await get_url_image(card.type_image), height=48),
			TextCell(cost),
			TextCell(card.name),
			TextCell(last_cell, horizontal_align="right")
		])
		card_color = card.color.blend(Color(background_color), 0.5)
		for cell in table.rows[len(table.rows) - 1]:
			cell.background = card_color.hex
	image = table.render()

	border_image = Image.new('RGBA', (image.size[0] + (border_size * 2), image.size[1] + border_size), color=trim_color)
	image = paste_image(border_image, image, border_size, 0)

	image.save(filename, format="PNG")

	return filename

# from vpk/panorama/styles/dotastyles.css
neutral_tier_text_colors = {
	"1": "#BEBEBE",
	"2": "#92E47E",
	"3": "#7F93FC",
	"4": "#D57BFF",
	"5": "#FFE195",
}

# from in-game screenshot
neutral_tier_colors = {
	"1": "#958a97",
	"2": "#0ea243",
	"3": "#4c6ee8",
	"4": "#9b2bf6",
	"5": "#e47b17",
}

# taken from https://stackoverflow.com/questions/4998427
def grouper(values, N):
	return [values[n:n+N] for n in range(0, len(values), N)]

async def draw_neutralitems_tier(selected_tier, all_neutral_items):
	items = list(filter(lambda i: i.neutral_tier == str(selected_tier), all_neutral_items))
	table = Table(background=background_color)
	for item in items:
		table.add_row([
			ImageCell(img=await get_item_image(item.id)),
			TextCell(item.localized_name, font_size=30, padding=10)
		])
	image = table.render()
	
	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)
	
	return fp
	
async def draw_neutralitems(selected_tier, all_neutral_items):
	if selected_tier is not None:
		return await draw_neutralitems_tier(selected_tier, all_neutral_items)

	items_per_row = 6
	table = Table(background=trim_color)
	for tier in range(1, 6):
		header_row = [ColorCell(color=background_color) for i in range(items_per_row)]
		header_row[0] = TextCell(f"Tier {tier}", color=neutral_tier_text_colors[str(tier)], font_size=25, padding=[10, 0, 10, 10], background=background_color)
		table.add_row(header_row)
		items = list(filter(lambda i: i.neutral_tier == str(tier), all_neutral_items))
		item_img_cells = []
		for item in items:
			item_img_cells.append(ImageCell(img=await get_item_image(item.id)))
		new_rows = grouper(item_img_cells, items_per_row)
		for row in new_rows:
			table.add_row(row)
		footer_row = [ColorCell(color=trim_color, height=20) for i in range(items_per_row)]
		table.add_row(footer_row)

	image = table.render()

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp

def get_poly_points(n, radius, origin=(0, 0), radius_percentages=None):
	radii = [radius for i in range(n)]
	if radius_percentages:
		radii = [radius * radius_percentages[i] for i in range(n)]
	rot_start = 0 - (math.pi / 2)
	return [
		(math.cos(rot_start + th) * radii[j] + origin[0], 
		 math.sin(rot_start + th) * radii[j] + origin[1]) 
		for j, th in enumerate([i * (2 * math.pi) / n for i in range(n)])
	]

def draw_poly_label(draw, point, center, text):
	font = ImageFont.truetype(settings.resource("images/arial_unicode_bold.ttf"), 16)
	font_size = font.getsize(text)
	point = list(point)
	if point[0] < center[0]:
		point[0] -= font_size[0]
	if point[1] < center[1]:
		point[1] -= font_size[1]
	if point[0] == center[0]:
		point[0] -= font_size[0] / 2
	if point[1] == center[1]:
		point[1] -= font_size[1] / 2
	draw.text(tuple(point), text, font=font, fill="#ffffff")

def draw_polygraph(values, labels):
	size = (500, 500)
	polygon_radius = 175
	point_count = len(values)

	center = (size[0] / 2, size[1] / 2)

	image = Image.new('RGBA', size)
	draw = ImageDraw.Draw(image)
	draw.rectangle([0, 0, image.size[0], image.size[1]], fill="#23272A")

	points = get_poly_points(point_count, polygon_radius, center)

	draw.polygon(points, fill="#2C2F33", outline="#111111")
	for point in points:
		draw.line((center[0], center[1], point[0], point[1]), fill="#111111")

	for i in range(len(points)):
		draw_poly_label(draw, points[i], center, labels[i])

	image2 = Image.new('RGBA', size)
	draw2 = ImageDraw.Draw(image2)
	data_points = get_poly_points(point_count, polygon_radius, center, values)
	draw2.polygon(data_points, fill="#FFDF0044", outline="#FFDF00")
	for p in data_points:
		dot_rad = 2
		draw2.ellipse([(p[0] - dot_rad, p[1] - dot_rad), (p[0] + dot_rad, p[1] + dot_rad)], fill="#FFDF00")
	image = paste_image(image, image2, 0, 0)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp

async def draw_herostatstable(table_args, hero_stat_categories, leveled_hero_stats):

	category = None
	for cat in hero_stat_categories:
		if any(stat["stat"] == table_args.stat for stat in cat["stats"]):
			category = cat
			break
	if category is None:
		raise UserError("Couldn't find referenced stat")

	stats = category["stats"]

	# sort / get data 
	hero_data = leveled_hero_stats[table_args.hero_level]
	hero_data = sorted(hero_data, key=lambda hero: hero.get(table_args.stat), reverse=not table_args.reverse)
	hero_data = hero_data[0:table_args.hero_count]

	table = Table(border_size=10)

	stat_highlight_color = trim_color
	table_background = background_color
	table_border_color = "#222222"

	header_row = [ TextCell("") ]
	for stat in stats:
		header_row.append(SlantedTextCell(
			stat["name"],
			font_size=20,
			background=stat_highlight_color if stat["stat"] == table_args.stat else table_background,
			border_color=table_border_color,
			border_size=4,
			rotation=45))
	
	header_height = max(cell.height for cell in header_row)
	padding_right = int(header_height / math.tan(header_row[-1].rotation_rad))
	table.border_size[1] = padding_right

	table.add_row(header_row)

	i = 0
	for hero in hero_data:
		cell_background = table_background
		#cell_background = stat_highlight_color if i % 2 else table_background
		new_row = [ ImageCell(img=await get_hero_icon(hero.get("id")), padding=3, background=table_background) ]
		for stat in stats:
			value = hero.get(stat["stat"])
			if stat.get("display") == "resistance_percentage":
				value = 100 * (1 - value)
			if stat.get("display") == "int":
				value = round(value)
			value = f"{value:.2f}"
			value = re.sub("\.0+$", "", value)
			if stat.get("display") == "resistance_percentage":
				value += "%"
			new_row.append(TextCell(
				value, 
				font_size=16, 
				padding=10,
				background=stat_highlight_color if stat["stat"] == table_args.stat else cell_background))
		table.add_row(new_row)
		i += 1

	image = table.render()

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp