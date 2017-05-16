from __main__ import settings, botdata
from PIL import Image, ImageDraw, ImageFont

table_font = settings.resource("images/table_font.ttf")

# if specified, padding should be a 4 element list, or an int
# 4 element list is left, top, right, bottom
def get_padding(kwargs, default=0):
	padding = kwargs.get("padding", default)
	if isinstance(padding, int):
		padding = [ padding, padding, padding, padding ]
	if 'padding_top' in kwargs:
		padding[0] = kwargs['padding_top']
	if 'padding_right' in kwargs:
		padding[1] = kwargs['padding_right']
	if 'padding_bottom' in kwargs:
		padding[2] = kwargs['padding_bottom']
	if 'padding_left' in kwargs:
		padding[3] = kwargs['padding_left']
	return padding

class Cell:
	def __init__(self, **kwargs):
		self.width = kwargs.get('width')
		self.height = kwargs.get('height')

class ColorCell(Cell):
	def __init__(self, **kwargs):
		Cell.__init__(self, **kwargs)
		self.color = kwargs.get('color', '#ffffff')

	def render(self, draw, image, x, y, width, height):
		draw.rectangle([x, y, x + width - 1, y + height - 1], fill=self.color)

class TextCell(Cell):
	def __init__(self, text, **kwargs):
		Cell.__init__(self, **kwargs)
		if not text:
			text = ""
		self.text = str(text)
		if isinstance(text, int) and 'horizontal_align' not in kwargs:
			kwargs['horizontal_align'] = 'center'
		self.color = kwargs.get('color', '#ffffff')
		self.background = kwargs.get('background')
		self.font = ImageFont.truetype(table_font, kwargs.get("font_size", 28))

		self.horizontal_align = kwargs.get('horizontal_align', 'left') # left center right
		self.vertical_align = kwargs.get('vertical_align', 'middle') # top middle bottom

		self.padding = get_padding(kwargs, [ 0, 5, 0, 5 ])
		self.text_size = self.font.getsize(self.text)
		if not self.width:
			self.width = self.padding[1] + self.text_size[0] + self.padding[3]
		if not self.height:
			self.height = self.padding[0] + self.text_size[1] + self.padding[2]

	def render(self, draw, image, x, y, width, height):
		if self.background:
			draw.rectangle([x, y, x + width - 1, y + height - 1], fill=self.background)

		x_loc = {
			'left': x + self.padding[3],
			'center': int(x + (width / 2) - (self.text_size[0] / 2)),
			'right': x + width - self.padding[1] - self.text_size[0]
		}[self.horizontal_align]
		y_loc = {
			'top': y + self.padding[0],
			'middle': int(y + (height / 2) - (self.font.size / 2) - 5),
			'bottom': y + height - self.padding[2] - self.font.size
		}[self.vertical_align]

		draw.text((x_loc, y_loc), self.text, font=self.font, fill=self.color)


class ImageCell(Cell):
	def __init__(self, **kwargs):
		Cell.__init__(self, **kwargs)
		self.image = kwargs.get('image', kwargs.get('img'))
		if not self.image:
			return # no image, so this is basically an empty cell
		if isinstance(self.image, str): # prolly a path to an image
			self.image = Image.open(self.image)

		if (not self.width) and (not self.height):
			self.width = self.image.width
			self.height = self.image.height
		elif not self.width:
			self.width = int(self.image.width * (self.height / self.image.height))
		elif not self.height:
			self.height = int(self.image.height * (self.width / self.image.width))
		# else both were set

	def render(self, draw, image, x, y, width, height):
		if not self.image:
			return # no image, so this is basically an empty cell
		actual_image = self.image.resize((self.width, self.height), Image.ANTIALIAS)
		image.paste(actual_image, (x, y))


class Table:
	def __init__(self, background=None):
		self.rows = []
		self.background = background

	def add_row(self, row):
		self.rows.append(row)

	def render(self):
		row_height = []
		for row in self.rows:
			height = None
			for cell in row:
				if cell.height:
					if not height or  height < cell.height:
						height = cell.height
			row_height.append(height)

		column_count = len(self.rows[0])
		column_width = []
		for col in range(column_count):
			width = None
			for row in self.rows:
				if row[col].width:
						if not width or  width < row[col].width:
							width = row[col].width
			column_width.append(width)

		image = Image.new('RGBA', (sum(column_width), sum(row_height)))
		draw = ImageDraw.Draw(image)
		if self.background:
			draw.rectangle([0, 0, image.size[0], image.size[1]], fill=self.background)

		y = 0
		for row in range(len(self.rows)):
			x = 0
			for column in range(column_count):
				self.rows[row][column].render(draw, image, x, y, column_width[column], row_height[row])
				# draw.rectangle([x, y, x + column_width[column], y + row_height[row]], outline="red")
				x += column_width[column]
			y += row_height[row]

		return image
