from __main__ import settings, botdata, httpgetter
import aiohttp
import asyncio
import async_timeout
import sys
from PIL import Image, ImageDraw
from .tabledraw import Table, ImageCell, TextCell, ColorCell
from io import BytesIO

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
	return Image.open(await httpgetter.get(hero_infos[hero_id]["image"], "bytes", cache=True))

async def get_hero_icon(hero_id):
	return Image.open(await httpgetter.get(hero_infos[hero_id]["icon"], "bytes", cache=True))

async def get_item_image(item_id):
	return Image.open(await httpgetter.get(item_infos[item_id]["icon"], "bytes", cache=True))

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
def paste_image(image1, image2, x, y):
	temp_image = Image.new("RGBA", image1.size)
	temp_image.paste(image2, (x, y))
	return Image.alpha_composite(image1, temp_image)

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

# places a hero icon on the map at the indicated x/y using the dota coordinant system
# scale is how much to scale the icon
async def place_hero_on_map(map_image, hero_id, x, y, icon_scale=1):
	scale = map_image.width / 128
	x = (x - 64) * scale
	y = (128 - (y - 64)) * scale
	icon = await get_hero_icon(hero_id)
	if icon_scale != 1:
		icon = icon.resize((int(icon.width * icon_scale), int(icon.height * icon_scale)), Image.ANTIALIAS)
	return paste_image(map_image, icon, int(x - (icon.width / 2)), int(y - (icon.height / 2)))


async def create_lanes_map(match):
	image = Image.open(settings.resource("images/dota_map.png"))

	# image = await place_hero_on_map(image, 34, 10, 10, icon_scale=1.5)
	player = match["players"][0]
	for x in player["lane_pos"]:
		for y in player["lane_pos"][x]:
			image = await place_hero_on_map(image, player["hero_id"], int(x), int(y), icon_scale=1.5)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)

	return fp

async def create_lanes_gif(match):
	ms_per_second = 100

	map_image = Image.open(settings.resource("images/dota_map.png"))
	map_image = map_image.resize((256, 256), Image.ANTIALIAS)
	frames = [map_image]

	done = False
	i = 0
	while not done:
		image = map_image.copy()
		for player in match["players"]:
			point = player["playerUpdatePositionEvents"][i]
			if point["time"] >= 600:
				done = True
				break
			image = await place_hero_on_map(image, player["hero"], point["x"], point["y"], icon_scale=0.75)
		if not done:
			frames.append(image)
		i += 1

	frames.append(map_image)

	print(map_image.info)

	increment = 1
	file_size = 10
	while file_size > 8:
		fp = BytesIO()
		frames[0].save(fp, save_all=True, format="GIF", append_images=frames[0::increment], duration=ms_per_second * increment, optimize=True)
		file_size = fp.getbuffer().nbytes / 1000000
		print(f"bytes: {file_size:.2f} MB")
		increment += 1

	fp.seek(0)
	return fp


	