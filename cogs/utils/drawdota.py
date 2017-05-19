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

async def get_item_image(item_id):
	return Image.open(await httpgetter.get(item_infos[item_id]["icon"], "bytes", cache=True))

# async def get_hero_image(hero_id):
# 	return Image.open(hero_infos[hero_id]["image"])

# async def get_item_image(item_id):
# 	return Image.open(item_infos[item_id]["icon"])

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
