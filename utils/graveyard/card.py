import re
from .imagetools import Color

class CardSet():
	def __init__(self, data):
		self.data = data
		self.id = data["set_info"]["set_id"]
		self.version = data["version"]
		self.name = data["set_info"]["name"]["english"]

	@classmethod
	def from_json(cls, card_sets_data):
		sets = []
		for data in card_sets_data:
			sets.append(CardSet(data))
		return sets


class CardRef():
	def __init__(self, data):
		self.data = data
		self.id = data["card_id"]
		self.ref_type = data["ref_type"] # one of CARD_REF_TYPES
		self.count = data.get("count")
		self.card = None # updated after cards are generated


class Card():
	def __init__(self, data, card_set):
		self.data = data
		self.set = card_set
		self.id = data.get("card_id")
		self.type = data.get("card_type") # one of CARD_TYPES
		self.sub_type = data.get("sub_type") # one of CARD_SUB_TYPES
		self.name = data.get("card_name", {}).get("english")
		self.text = data.get("card_text", {}).get("english")
		if self.text:
			self.text = re.sub(r"<span [^>]+>([^<]+)</span>", r"**\1**", self.text)
			self.text = re.sub(r"<(br|BR)/?>", "\n", self.text)
		self.mini_image = data.get("mini_image", {}).get("default")
		self.large_image = data.get("large_image", {}).get("default")
		self.ingame_image = data.get("ingame_image", {}).get("default")
		self.color_name = None
		for key in CARD_COLOR_MAP:
			if data.get(f"is_{key}"):
				self.color_name = key
		self.references = list(map(lambda ref: CardRef(ref), data.get("references", [])))

		# other fields
		self.rarity = data.get("rarity") # one of CARD_RARITIES
		self.mana_cost = data.get("mana_cost")
		self.hit_points = data.get("hit_points")
		self.attack = data.get("attack")
		self.armor = data.get("armor")
		self.gold_cost = data.get("gold_cost")
		self.item_def = data.get("item_def")
		self.illustrator = data.get("illustrator")

	# gets all the references with the given ref_type
	def get_references(self, ref_type):
		return (r for r in self.references if r.ref_type == ref_type)

	# updates all of the references with the actual card
	def update_references(self, card_getter):
		for ref in self.references:
			ref.card = card_getter(ref.id)

	@property
	def color(self):
		if self.color_name:
			return CARD_COLOR_MAP[self.color_name]
		elif self.type == "Item":
			return CARD_COLOR_MAP["item"]
		else:
			return CARD_COLOR_MAP["default"]

	@property
	def type_image(self):
		type_name = None
		if self.type in CARD_TYPE_ICON_MAP:
			type_name = CARD_TYPE_ICON_MAP[self.type]
		if self.sub_type in CARD_TYPE_ICON_MAP:
			type_name = CARD_TYPE_ICON_MAP[self.sub_type]
		if type_name:
			return f"https://steamcdn-a.akamaihd.net/apps/artifact/images/deck_art/card_type_{type_name}.png"
		return None

	@classmethod
	def from_json(cls, cards_data, card_sets):
		cards = []
		for data in cards_data:
			card_set = next((card_set for card_set in card_sets if card_set.id == data["set_id"]), None)
			cards.append(Card(data, card_set))
		return cards

CARD_TYPES = [
	"Creep",
	"Hero",
	"Spell",
	"Improvement"
	"Item",

	"Ability",
	"Passive Ability",
	"Stronghold",
	"Pathing",
]

CARD_SUB_TYPES = [ # sub_types are only specified for Items
	"Accessory",
	"Armor",
	"Weapon",
	"Consumable",
	"Deed"
]

CARD_REF_TYPES = [
	"active_ability",
	"passive_ability",
	"includes",
	"references"
]

CARD_RARITIES = [
	"Common",
	"Rare",
	"Uncommon"
]

# base_url is https://steamcdn-a.akamaihd.net/apps/artifact/images/deck_art/card_type_{specific}.png
CARD_TYPE_ICON_MAP = {
	"Creep": "creep",
	"Hero": "hero",
	"Spell": "spell",
	"Improvement": "improvement",

	"Armor": "armor",
	"Weapon": "weapon",
	"Consumable": "consumable",
	"Accessory": "health",
	"Deed": "consumable" 
}

CARD_COLOR_MAP = {
	"green": Color("#59753f"),
	"red": Color("#942e38"),
	"blue": Color("#225c7c"),
	"black": Color("#312a2d"),
	"item": Color("#df9a3b"),
	"default": Color("#706c67")
}

