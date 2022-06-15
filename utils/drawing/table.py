import math

from PIL import Image, ImageDraw, ImageFont
from utils.tools.globals import settings
from utils.drawing.imagetools import *

table_font = settings.resource("images/arial_unicode_bold.ttf")

# cache of table_font based on size
table_font_cache = {}

def get_table_font(size):
	if size not in table_font_cache:
		table_font_cache[size] = ImageFont.truetype(table_font, size)
	return table_font_cache[size]

# if specified, padding should be a 4 element list, or an int
# 4 element list is left, top, right, bottom
def get_padding(kwargs, default=0):
	if isinstance(kwargs, dict):
		padding = kwargs.get("padding", default)
	else:
		padding = kwargs
	if isinstance(padding, int):
		padding = [ padding, padding, padding, padding ]
	if isinstance(kwargs, int):
		return padding
	if 'padding_top' in kwargs:
		padding[0] = kwargs['padding_top']
	if 'padding_right' in kwargs:
		padding[1] = kwargs['padding_right']
	if 'padding_bottom' in kwargs:
		padding[2] = kwargs['padding_bottom']
	if 'padding_left' in kwargs:
		padding[3] = kwargs['padding_left']
	return padding

def tuplediff(tuple1, tuple2):
	return tuple(map(lambda i, j: i - j, tuple1, tuple2))

class Cell:
	def __init__(self, **kwargs):
		self.width = kwargs.get('width', 0)
		self.height = kwargs.get('height', 0)
		self.background = kwargs.get('background')
		self.border_size = kwargs.get('border_size', 0)
		self.border_color = kwargs.get('border_color', "#ffffff")

	def base_render(self, draw, image, x, y, width, height):
		# background
		if self.background:
			draw.rectangle([x, y, x + width - 1, y + height - 1], fill=self.background)

		# draw cell
		image, draw = self.render(draw, image, x, y, width, height)

		# border
		if self.border_size:
			# for now, this only draws the right and bottom lines
			z = self.border_size
			draw.line((x + width - z, y, x + width - z, y + height - z), width=z, fill=self.border_color)
			draw.line((x, y + height - z, x + width - z, y + height - z), width=z, fill=self.border_color)

		return image, draw

	def render(self, draw, image, x, y, width, height):
		return image, draw

# an empty cell that takes up space but doesn't get drawn
class EmptyCell(Cell):
	def __init__(self, **kwargs):
		Cell.__init__(self, **kwargs)

# a wrapper class to make the color specifying simpler
class ColorCell(Cell):
	def __init__(self, **kwargs):
		self.color = kwargs.get('color', '#ffffff')
		if "background" not in kwargs:
			kwargs["background"] = self.color
		Cell.__init__(self, **kwargs)

class CustomRenderCell(Cell):
	def __init__(self, **kwargs):
		self.render_func = kwargs.get('render_func')
		Cell.__init__(self, **kwargs)
	
	def render(self, draw, image, x, y, width, height):
		if self.render_func:
			return self.render_func(draw, image, x, y, width, height)
		return image, draw

class DoubleCell(Cell):
	def __init__(self, cell1, cell2, **kwargs):
		Cell.__init__(self, **kwargs)
		self.cell1 = cell1
		self.cell2 = cell2
		if not self.width:
			self.width = max(cell1.width, cell2.width)
		if not self.height:
			self.height = cell1.height + cell2.height
		self.cell1_percent = 1.0 * cell1.height / (cell1.height + cell2.height)
		self.cell2_percent = 1.0 * cell2.height / (cell1.height + cell2.height)

	def render(self, draw, image, x, y, width, height):
		self.cell1.render(draw, image, x, y, width, height * self.cell1_percent)
		self.cell2.render(draw, image, x, y + (height * self.cell1_percent), width, height * self.cell2_percent)
		return image, draw

class TextCell(Cell):
	def __init__(self, text, **kwargs):
		Cell.__init__(self, **kwargs)
		if text is None:
			text = ""
		self.text = str(text)
		if isinstance(text, int) and 'horizontal_align' not in kwargs:
			kwargs['horizontal_align'] = 'center'
		self.color = kwargs.get('color', '#ffffff')
		self.font = get_table_font(kwargs.get("font_size", 28))
		self.wrap = kwargs.get('wrap', False)

		self.horizontal_align = kwargs.get('horizontal_align', 'left') # left center right
		self.vertical_align = kwargs.get('vertical_align', 'middle') # top middle bottom

		self.padding = get_padding(kwargs, [ 0, 5, 0, 5 ])
		self.text_size = self.font.getsize(self.text)
		if not self.width:
			self.width = self.padding[1] + self.text_size[0] + self.padding[3]
		if not self.height:
			self.height = self.padding[0] + self.text_size[1] + self.padding[2]

	def render(self, draw, image, x, y, width, height):
		actual_width = (width - self.padding[3]) - self.padding[1]
		words = self.text.split(" ")
		if self.wrap:
			lines = [words[0]]
			words = words[1:]
			i = 0
			for word in words:
				if self.font.getsize(lines[i] + " " + word)[0] < actual_width:
					lines[i] += " " + word
				else:
					i += 1
					lines.append(word)
		else:
			lines = [ " ".join(words) ]

		line_padding = 5

		total_height = self.font.size + ((len(lines) - 1) * (line_padding + self.font.size))

		for i in range(0, len(lines)):
			text_size = self.font.getsize(lines[i])
			x_loc = {
				'left': x + self.padding[3],
				'center': int(x + (width / 2) - (text_size[0] / 2)),
				'right': x + width - self.padding[1] - text_size[0]
			}[self.horizontal_align]

			y_diff = i * (self.font.size + line_padding)

			y_loc = {
				'top': y + self.padding[0] + y_diff,
				'middle': int(y + (height / 2) - (total_height / 2) + y_diff - 5),
				'bottom': y + height - self.padding[2] - (total_height - y_diff)
			}[self.vertical_align]


			draw.text((x_loc, y_loc), lines[i], font=self.font, fill=self.color)
		return image, draw


class SlantedTextCell(Cell):
	def __init__(self, text, **kwargs):
		Cell.__init__(self, **kwargs)
		if text is None:
			text = ""
		self.text = str(text)
		self.color = kwargs.get('color', '#ffffff')
		self.font = get_table_font(kwargs.get("font_size", 28))
		self.border_color = kwargs.get('border_color', self.color)
		self.border_size = kwargs.get('border_size', 2)
		self.rotation = kwargs.get('rotation', 45)
		self.rotation_rad = math.radians(self.rotation)

		self.padding = get_padding(kwargs, [ 10, 10, 10, 10 ])
		self.text_size = self.font.getsize(self.text)
		if not self.width:
			self.width = self.padding[1] + self.text_size[1] + self.padding[3]
		if not self.height:
			self.height = self.padding[0] + int(math.sin(self.rotation_rad) * self.text_size[0]) + self.text_size[1] + self.padding[2]

	def base_render(self, draw, image, x, y, width, height):
		return self.render(draw, image, x, y, width, height)

	def render(self, draw, image, x, y, width, height):
		pos = (x, y + height)
		xshift = 0

		font_image_size = (self.text_size[0] + self.text_size[1], self.text_size[0] + self.text_size[1])
		font_pos = (int(self.text_size[1] / 2), self.text_size[0])
		font_center_pos = (font_pos[0], font_pos[1] + int(self.text_size[1] / 2))

		# background & border setup
		linestart = (pos[0] + width, pos[1])
		lineend = (linestart[0] + int(height / math.tan(self.rotation_rad)), linestart[1] - height)
		box_top = (tuplediff(lineend, (width, 0)), lineend)
		box_bottom = (tuplediff(linestart, (width, 0)), linestart)
		if self.background:
			draw.polygon([box_top[0], box_top[1], box_bottom[1], box_bottom[0]], fill=self.background)

		# border
		draw.line((tuplediff(linestart, (self.border_size, 0)), tuplediff(lineend, (self.border_size, 0))), fill=self.border_color, width=self.border_size)
		draw.line(box_top, fill=self.border_color, width=self.border_size)
		draw.line((tuplediff(box_bottom[0], (0 - self.border_size, self.border_size)), tuplediff(box_bottom[1], (0, self.border_size))), fill=self.border_color, width=self.border_size)

		# text
		text_image = Image.new('RGBA', font_image_size)
		text_draw = ImageDraw.Draw(text_image)
		text_draw.text(font_pos, self.text, font=self.font, fill=self.color)
		text_image = text_image.rotate(self.rotation, resample=Image.BILINEAR, center=font_center_pos)

		font_destination = tuplediff(pos, font_pos)
		font_destination = (font_destination[0] + int(width / 2) + xshift, font_destination[1] - int(self.text_size[1] / 2) - self.padding[2])
		image = paste_image(image, text_image, int(font_destination[0]), int(font_destination[1]))
		draw = ImageDraw.Draw(image)


		return image, draw



class ImageCell(Cell):
	def __init__(self, **kwargs):
		Cell.__init__(self, **kwargs)
		self.image = kwargs.get('image', kwargs.get('img'))
		if not self.image:
			return # no image, so this is basically an empty cell
		if isinstance(self.image, str): # prolly a path to an image
			self.image = Image.open(self.image)

		self.padding = get_padding(kwargs, 0)

		if (not self.width) and (not self.height):
			self.width = self.image.width
			self.height = self.image.height
		elif not self.width:
			self.width = int(self.image.width * (self.height / self.image.height))
		elif not self.height:
			self.height = int(self.image.height * (self.width / self.image.width))
		self.width += self.padding[1] + self.padding[3]
		self.height += self.padding[0] + self.padding[2]
		# else both were set

	def render(self, draw, image, x, y, width, height):
		if not self.image:
			return image, draw # no image, so this is basically an empty cell
		actual_image = self.image.resize((self.width - (self.padding[1] + self.padding[3]), self.height - (self.padding[0] + self.padding[2])), Image.ANTIALIAS)
		image = paste_image(image, actual_image, x + self.padding[3], y + self.padding[0])
		draw = ImageDraw.Draw(image)
		return image, draw
		


class Table:
	def __init__(self, background=None, border_size=0):
		self.rows = []
		self.background = background
		self.border_size = get_padding(border_size)

	def add_row(self, row):
		self.rows.append(row)

	def render(self):
		row_height = []
		for row in self.rows:
			height = None
			for cell in row:
				if cell and cell.height:
					if not height or  height < cell.height:
						height = cell.height
			row_height.append(height)

		column_count = max(map(len, self.rows))
		column_width = []
		for col in range(column_count):
			width = 0
			for row in self.rows:
				if len(row) <= col or row[col] is None:
					continue
				if row[col].width:
						if not width or  width < row[col].width:
							width = row[col].width
			column_width.append(width)

		image = Image.new('RGBA', (int(sum(column_width) + (self.border_size[1] + self.border_size[3])), int(sum(row_height) + self.border_size[0] + self.border_size[2])))
		draw = ImageDraw.Draw(image)
		if self.background:
			draw.rectangle([0, 0, image.size[0], image.size[1]], fill=self.background)

		y = self.border_size[0]
		for row in range(len(self.rows)):
			x = self.border_size[3]
			for column in range(column_count):
				if len(self.rows[row]) <= column or self.rows[row][column] is None:
					continue
				image, draw = self.rows[row][column].base_render(draw, image, x, y, column_width[column], row_height[row])
				x += column_width[column]
			y += row_height[row]

		return image
