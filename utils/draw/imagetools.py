import colorsys
import re
from collections import OrderedDict

import colorgram
from PIL import Image


def rgb_to_hsv(rgb):
	rgb = tuple(map(lambda v: v / 255.0, rgb))
	hsv = colorsys.rgb_to_hsv(*rgb)
	return tuple(map(lambda v: int(v * 255), hsv))
	
def hsv_to_rgb(hsv):
	hsv = tuple(map(lambda v: v / 255.0, hsv))
	rgb = colorsys.hsv_to_rgb(*hsv)
	return tuple(map(lambda v: int(v * 255), rgb))


class Color():
	def __init__(self, value):
		if isinstance(value, Color):
			value = value.hex
		if isinstance(value, str):
			if not re.match(r"#?[0-9a-fA-F]{6}$", value):
				raise ValueError("Color given invalid hex color")
			value = value.lstrip("#")
			lv = len(value)
			self.r, self.g, self.b = tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
		elif isinstance(value, tuple):
			if len(value) == 3:
				self.r, self.g, self.b = value
			elif len(value) == 4: # throw away alpha here
				self.r, self.g, self.b, a = value
			else:
				raise ValueError("Wrong number of values in tuple")
		else:
			raise ValueError("Unexpected type given to Color constructor")

	@property
	def integer(self):
		return int(self.hex[1:], 16)

	@property
	def hex(self):
		return "#{0:02x}{1:02x}{2:02x}".format(self.r, self.g, self.b)

	@property
	def rgb_tuple(self):
		return (self.r, self.g, self.b)

	@property
	def hsv_tuple(self):
		return rgb_to_hsv(self.rgb_tuple)

	@property
	def h(self):
		return self.hsv_tuple[0]

	@property
	def s(self):
		return self.hsv_tuple[1]

	@property
	def v(self):
		return self.hsv_tuple[2]

	def rgba_tuple(self, a):
		return (self.r, self.g, self.b, a)

	def __repr__(self):
		return self.hex

	def __eq__(self, other):
		if isinstance(self, other.__class__):
			return self.__dict__ == other.__dict__
		return False

	def __hash__(self):
		return self.integer

	# blends this color with another color (of the given opacity) and returns the result
	def blend(self, color, opacity=0.5):
		my_op = 1 - opacity
		return Color((
			int((self.r * my_op) + (color.r * opacity)),
			int((self.g * my_op) + (color.g * opacity)),
			int((self.b * my_op) + (color.b * opacity))
		))

# gets a number representing how far apart the 2 colors are
def color_diff(c1, c2):
	return abs(c1.r - c2.r) + abs(c1.g - c2.g) + abs(c1.b - c2.b)

# colorizes a pixel based on the best fit of the old color from a pallete, matching it to the new color
def colorize_single(converter, pixel_color):
	old = min(converter, key=lambda c: color_diff(c, pixel_color))
	new = converter[old]

	return Color(hsv_to_rgb((
		new.h,
		pixel_color.s,
		pixel_color.v
	)))


# takes in 2 image filenames and spits out a third colorized one
# the colors from the first one are used to fill in the shape of the second one
def colorize_image(filename1, filename2, out_filename):
	pallete_size = 5

	new_pallete = colorgram.extract(filename1, pallete_size)
	old_pallete = colorgram.extract(filename2, pallete_size)

	new_pallete = list(map(lambda c: Color(c.rgb), new_pallete))
	old_pallete = list(map(lambda c: Color(c.rgb), old_pallete))

	pallete_dict = OrderedDict()

	for i in range(pallete_size):
		pallete_dict[old_pallete[i]] = new_pallete[i]

	# go edit pixels now that the dict has been built
	image = Image.open(filename2).convert("RGBA")
	pixels = image.load()

	width, height = image.size

	for j in range(height):
		for i in range(width):
			alpha = pixels[i, j][3]
			result_color = colorize_single(pallete_dict, Color(pixels[i, j]))
			pixels[i, j] = result_color.rgba_tuple(alpha)

	image.save(out_filename, format="PNG")


# pastes image 2 onto image 1, preserving alpha/transparency
# this will close the first image that was passed in, as it is assumed that this will replace it
def paste_image(image1, image2, x=0, y=0):
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
