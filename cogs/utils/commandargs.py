import re
import discord.ext.commands

def clean_input(t):
	return re.sub(r'[^a-z1-9\s]', r'', str(t).lower())

class InputParser():
	def __init__(self, text):
		self.text = text

	def trim(self):
		self.text = self.text.strip()
		self.text = re.sub(r"\s+", " ", self.text)

	def take_regex(self, pattern, add_word_boundary=True):
		pattern = f"\\b(?:{pattern})\\b"
		match = re.search(pattern, self.text, re.IGNORECASE)
		if match is None:
			return None
		self.text = re.sub(pattern, "", self.text, count=1)
		self.trim()
		return match.group(0)


class QueryArg():
	def __init__(self, name, args_dict={}, post_filter=None):
		self.name = name
		self.args_dict = args_dict
		self.value = None
		self.post_filter = None

	def parse(self, text):
		for key in self.args_dict:
			if re.match(key, text):
				self.value = self.args_dict[key]

	def has_value(self):
		return self.value is not None

	def regex(self):
		return "|".join(map(lambda k: f"(?:{k})", self.args_dict.keys()))

	def to_query_arg(self):
		return f"{self.name}={self.value}"

	def check_post_filter(self, p):
		if (not self.has_value()) or (self.post_filter is None):
			return True
		return self.post_filter(p)

# added manually
class SimpleQueryArg(QueryArg):
	def __init__(self, name, value):
		super().__init__(name)
		self.value = value


class TimeSpanArg(QueryArg):
	def __init__(self):
		super().__init__("date")
		self.count = None
		self.chunk = None

	def parse(self, text):
		match = re.match(self.regex(), text)
		self.count = int(match.group(2) or "1")
		self.chunk = match.group(3)
		self.value = self.days

	@property
	def days(self):
		count = {
			"day": 1,
			"week": 7,
			"month": 30,
			"year": 365
		}[self.chunk]
		return count * self.count

	def regex(self):
		return r"(?:in|over)? ?(?:the )?(this|last|past)? ?(\d+)? (day|week|month|year)s?"

class MatchFilter():
	def __init__(self, args=[]):
		self.args = args

	@classmethod
	async def convert(cls, ctx, argument):
		parser = InputParser(argument)
		args = [
			QueryArg("win", {
				r"wins?|won|victory": 1,
				r"loss|lost|losses|defeat": 0
			}),
			QueryArg("is_radiant", {
				r"(as|on)? ?radiant": 1,
				r"(as|on)? ?dire": 0
			}),
			QueryArg("lobby_type", {
				r"ranked": 7,
				r"(un|non)-?ranked": 0
			}),
			QueryArg("lane_role", {
				r"safe( ?lane)?": 1,
				r"mid(dle)?( ?lane)?": 2,
				r"(off|hard)( ?lane)?": 3,
				r"jungl(e|ing)": 4
			}, lambda p: not p.get("is_roaming")),
			QueryArg(None, {
				r"roam(ing)?|gank(ing)?": True
			}, lambda p: p.get("is_roaming")),
			TimeSpanArg()
		]
		for arg in args:
			value = parser.take_regex(arg.regex(), arg.parse)
			if value:
				arg.parse(value)
		if parser.text:
			raise discord.ext.commands.BadArgument()
		return cls(args)

	def add_simple_arg(self, name, value):
		self.args.append(SimpleQueryArg(name, value))

	def to_query_args(self):
		return "&".join(map(lambda a: a.to_query_arg(), filter(lambda a: a.has_value(), self.args)))

	def post_filter(self, p):
		return all(a.post_filter_check() for a in self.args)

