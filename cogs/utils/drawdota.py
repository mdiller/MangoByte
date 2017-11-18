from __main__ import settings, botdata, httpgetter
import aiohttp
import asyncio
import async_timeout
import sys
import subprocess
import os
import numpy
from PIL import Image, ImageDraw, ImageFont
from .tabledraw import Table, ImageCell, TextCell, ColorCell
from io import BytesIO
from .helpers import run_command, get_pretty_time, read_json, UserError

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

async def get_hero_image(hero_id):
	try:
		return Image.open(await httpgetter.get(hero_infos[hero_id]["image"], "bytes", cache=True))
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_hero_icon(hero_id):
	try:
		return Image.open(await httpgetter.get(hero_infos[hero_id]["icon"], "bytes", cache=True))
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_item_image(item_id):
	try:
		return Image.open(await httpgetter.get(item_infos[item_id]["icon"], "bytes", cache=True))
	except KeyError:
		return Image.new('RGBA', (10, 10), (0, 0, 0, 0))

async def get_item_images(player):
	images = []
	for i in range(0, 6):
		item = player.get(f"item_{i}")
		if item:
			images.append(await get_item_image(item))
	if len(images) == 0:
		return None

	widths, heights = zip(*(i.size for i in images))
	result = Image.new("RGBA", (sum(widths), max(heights)))

	x = 0
	for i in range(len(images)):
		result.paste(images[i], (x, 0))
		x += widths[i]
	return result


def get_lane(player):
	lane_dict = { 1: "Bot", 3: "Top" }
	lane_role_dict = { 1: "Safe", 2: "Mid", 3: "Off", 4: "Jungle" }
	if 'is_roaming' in player and player['is_roaming']:
		return "Roaming"
	elif player.get('lane') in lane_dict:
		return f"{lane_role_dict[player['lane_role']]}({lane_dict[player['lane']]})"
	else:
		return lane_role_dict[player.get('lane_role')]

# pastes image 2 onto image 1, preserving alpha/transparency
# this will close the first image that was passed in, as it is assumed that this will replace it
def paste_image(image1, image2, x, y):
	temp_image = Image.new("RGBA", image1.size)
	temp_image.paste(image2, (x, y))
	return Image.alpha_composite(image1, temp_image)

# colors an image with one single color for all the pixes that are currently not transparent
def color_image(image, color):
	image = image.copy()
	pixels = image.load()

	for y in range(image.height):
		for x in range(image.width):
			if pixels[x, y][3] > 128:
				pixels[x, y] = color
	return image

# removes semi transparent areas of an image and replaces them with either transparent or the given color
def remove_semi_transparent(image, color):
	image = image.copy()
	pixels = image.load()

	for y in range(image.height):
		for x in range(image.width):
			if pixels[x, y][3] > 128:
				p = pixels[x, y]
				pixels[x, y] = (p[0], p[1], p[2])
			else:
				pixels[x, y] = color
	return image

def outline_image(image, thickness, color):
	background = color_image(image, color)
	background = background.resize((image.width + (thickness * 2), image.height + (thickness * 2)))

	image = paste_image(background, image, thickness, thickness)
	return image


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

async def optimize_gif(uri, filename):

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
async def place_icon_on_map(map_image, icon, x, y):
	scale = map_image.width / 128
	x = (x - 64) * scale
	y = (128 - (y - 64)) * scale
	return paste_image(map_image, icon, int(x - (icon.width / 2)), int(y - (icon.height / 2)))


async def create_dota_gif(match, stratz_match, start_time, end_time, ms_per_second=100):
	uri = f"match_gif:{match['match_id']}:{start_time}:{end_time}:{ms_per_second}"

	reverse = end_time < start_time
	if reverse:
		temp = start_time
		start_time = end_time
		end_time = temp

	filename = httpgetter.cache.get_filename(uri)
	if filename and not settings.debug:
		return filename

	filename = await httpgetter.cache.new(uri, "gif")

	building_data = read_json(settings.resource("json/building_data.json"))

	map_image = Image.open(settings.resource("images/map/dota_map.png"))
	map_image = map_image.resize((256, 256), Image.ANTIALIAS)

	clock_bg_image = Image.open(settings.resource("images/map/clock_background.png"))
	font = ImageFont.truetype(settings.resource("images/table_font.ttf"), 16)

	match_start = -89
	if start_time < match_start:
		start_time = match_start
	if end_time > match["duration"]:
		end_time = match["duration"]

	players = []
	for player in stratz_match["players"]:
		positionEvents = player["playerUpdatePositionEvents"]
		deathEvents = player["deathEvents"]
		scale = 0.75
		icon = await get_hero_icon(player["hero"])
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
	current_runes = {}
	runes = {}
	for t in range(match_start, end_time + 1):
		events = filter(lambda e: e["time"] == t, stratz_match["runeEvents"])
		for e in filter(lambda e: e["time"] == t and e["action"] == 0, stratz_match["runeEvents"]):
			current_runes[e["id"]] = {
				"type": e["runeType"],
				"x": e["x"],
				"y": e["y"]
			}
		if t >= start_time and current_runes:
			runes[t] = current_runes.copy()
		for e in filter(lambda e: e["time"] == t and e["action"] == 1, stratz_match["runeEvents"]):
			if e["id"] in current_runes:
				del current_runes[e["id"]]
	# rune icons
	rune_icons = {}
	for i in range(0, 7):
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
				image = await place_icon_on_map(image, building["icon"], building["x"], building["y"])
		for player in players:
			icon = player["icon"].convert("LA") if player[t]["dead"] else player["icon"]
			image = await place_icon_on_map(image, icon, player[t]["x"], player[t]["y"])
		for rune in runes.get(t, {}):
			rune = runes[t][rune]
			image = await place_icon_on_map(image, rune_icons[rune["type"]], rune["x"], rune["y"])

		image = paste_image(image, clock_bg_image, (image.width // 2) - (clock_bg_image.width // 2), 0)
		draw = ImageDraw.Draw(image)
		clock_text = get_pretty_time(abs(t))
		clock_pos = ((image.width // 2) - (font.getsize(clock_text)[0] // 2), -1)		
		draw.text(clock_pos, clock_text, font=font, fill="#ffffff")

		image.save(process.stdin, "gif")
		image.close()

	process.stdin.close()
	process.wait()

	await optimize_gif(uri, filename)

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