import math
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from utils.drawing.table import get_table_font


# draws a graph with the given data points
# passed in lines are just lists of numbers, (y axis values), x axis is index
def drawgraph(lines, colors, labels):
	downscale_amount = 10
	height = 400
	width = 800

	height *= downscale_amount
	width *= downscale_amount

	font = get_table_font(12 * downscale_amount)
	# font = ImageFont.truetype("resource/images/arial_unicode_bold.ttf", 12 * downscale_amount)

	has_negative_y = min(map(min, lines)) < 0

	# the calculated highest/lowest value to use for the graph
	maxvalue = max(map(lambda line: max(map(abs, line)), lines))
	maxvalue += int(maxvalue * 0.1)
	round_digits = len(str(maxvalue)) - 2 # round to the nearest nice number
	round_adjust = math.pow(10, round_digits)
	maxvalue = int(math.ceil(maxvalue / round_adjust) * round_adjust)

	y_max = maxvalue
	x_max = max(map(len, lines)) - 1

	y_grid_line_count = 6
	if has_negative_y:
		y_grid_line_count //= 2
	y_grid_line_increment = y_max // (y_grid_line_count + 1)
	y_grid_lines = []
	for i in range(1, y_grid_line_count + 1):
		value = i * y_grid_line_increment
		y_grid_lines.append(value)
		if has_negative_y:
			y_grid_lines.append(-1 * value)

	x_axis_increment = 10
	x_grid_lines = []
	for i in range(1, x_max // x_axis_increment + 1):
		value = i * x_axis_increment
		x_grid_lines.append(value)

	image = Image.new("RGBA", (width, height))
	draw = ImageDraw.Draw(image)

	# draw background
	draw.rectangle([0, 0, image.size[0], image.size[1]], fill="#23272A")

	# draw midline
	midline_thickness = 4 * downscale_amount
	midline_y = (height // 2)
	draw.line((0, midline_y, width, midline_y), fill="#202225", width=midline_thickness)

	# draw gridlines
	for gridline in y_grid_lines:
		gridline_thickness = 2 * downscale_amount
		gridline_y = int(((y_max - gridline) / (y_max * (2 if has_negative_y else 1))) * height)
		draw.line((0, gridline_y, width, gridline_y), fill="#202225", width=gridline_thickness)
		text = f"{gridline:,d}"
		text_size = font.getsize(text)
		text_x = 20
		text_y = gridline_y - text_size[1] - (2 * downscale_amount)
		# draw.rectangle((text_x, text_y, text_x + text_size[0], text_y + text_size[1]))
		draw.text((text_x, text_y), text, font=font, fill="#727d8a")

	for gridline in x_grid_lines:
		gridline_thickness = 2 * downscale_amount
		gridline_x = int((gridline / x_max) * width)
		draw.line((gridline_x, 0, gridline_x, height), fill="#202225", width=gridline_thickness)
		text = f"{gridline}:00"
		text_size = font.getsize(text)
		text_padding = (5 * downscale_amount)
		text_x = gridline_x + text_padding
		text_y = height - text_size[1] - text_padding
		# draw.rectangle((text_x, text_y, text_x + text_size[0], text_y + text_size[1]))
		draw.text((text_x, text_y), text, font=font, fill="#727d8a")

	# draw lines
	line_thickness = 2 * downscale_amount
	for i in range(len(lines)):
		line = lines[i]
		color = colors[i]
		last_x = None
		last_y = None
		for i in range(len(line)):
			x = int((i / x_max) * width)
			y = int(((y_max - line[i]) / (y_max * (2 if has_negative_y else 1))) * height)

			if last_x is not None:
				draw.line((last_x, last_y, x, y), fill=color, width=line_thickness)

			last_x = x
			last_y = y

	# draw legend
	legend_text_adjustment = font.getsize(labels[0])[1] * -0.09
	legend_x = 50 * downscale_amount
	legend_y = 5 * downscale_amount
	legend_padding = (5 * downscale_amount)
	legend_spacing = max(map(lambda label: font.getsize(label)[1], labels)) + legend_padding
	legend_text_pad = 15 * downscale_amount
	for i in range(len(lines)):
		color = colors[i]
		label = labels[i]
		x = legend_x
		y = legend_y + (i * legend_spacing)

		# draw.rectangle((x, y, x + font.getsize(label)[0] + legend_text_pad, y + legend_spacing))
		dot_x = x + (legend_text_pad // 2)
		dot_y = y + (legend_spacing // 2)
		dot_radius = 5 * downscale_amount
		draw.ellipse([(dot_x - dot_radius, dot_y - dot_radius), (dot_x + dot_radius, dot_y + dot_radius)], fill=color)
		draw.text((x + legend_text_pad, y + (legend_padding // 2) + legend_text_adjustment), label, font=font, fill="#FFFFFF")


	if downscale_amount != 1:
		image = image.resize((width // downscale_amount, height // downscale_amount), Image.ANTIALIAS)

	fp = BytesIO()
	image.save(fp, format="PNG")
	fp.seek(0)
	return fp
	# image.save("out.png", format="PNG")


# TEST DATA
# line1 = [ 0, 146, -396, -677, -445, -481, -902, -1097, -33, -474, -801, -618, -550, 232, 708, 24, -1432, -4056, -3298, -2203, -147, -1423, -878, 1507, -205, 266, -1010, -468, 2080, 3856, 4479, 6769, 7951, 4922, 2960, 1805, 428, -3176, -3490, -4133, -3928, -4375, -3240, -3209, -2595, -2691, -3331, -3169, -3188, -3230, -3957, -6612, -8014, -8905, -8757, -9330, -9020, -3335, -223 ]
# line2 = [ 0, 339, -305, -344, -474, -200, -204, 50, 1678, 1051, 438, 448, 806, 2623, 3537, 2345, 1078, -2874, -749, 165, 3918, 2539, 3613, 6386, 667, 1282, -464, -214, 6377, 11922, 12350, 17866, 19061, 7225, 6839, 3033, -2857, -2154, -1797, -4180, -6234, -9626, -4107, -5728, -3195, -4408, -5550, -3300, -3734, -4152, -7747, -22968, -22652, -20976, -20758, -21390, -19123, -10725, -1136 ]
# drawgraph([line1, line2], ["#FFFF00", "#ADD8E6"], ["Gold", "Experience"])
