from __main__ import settings, botdata, loggingdb_session
from cogs.utils.helpers import *
from cogs.utils.clip import *



class MangoCog:
	def __init__(self, bot):
		self.bot = bot
		self.emoji_dict = read_json(settings.resource("json/emoji.json"))

	def get_emoji(self, key):
		return self.emoji_dict.get(key, f":{key}:")

	async def get_clip_try_types(self, clipid, trytypes, ctx):
		trytypes = trytypes.split("|")
		try:
			return await self.get_clip(clipid, ctx)
		except MissingClipType:
			while len(trytypes) > 0:
				try:
					return await self.get_clip("{}:{}".format(trytypes.pop(), clipid), ctx)
				except ClipNotFound:
					continue
		raise MissingClipType(clipid)

	async def get_clip(self, clipid, ctx):
		cliptypes = Clip.types_dict()

		match = re.search(f"^({'|'.join(cliptypes)}):(.*)$", clipid.replace("\n", " "))

		if not match:
			raise MissingClipType(clipid)

		return cliptypes[match.group(1)](match.group(2), self.bot, ctx)


	async def play_clip(self, clip, ctx):
		if isinstance(clip, str):
			clip = await self.get_clip(clip, ctx)

		audio = self.bot.get_cog("Audio")
		await (await audio.audioplayer(ctx)).queue_clip(clip, ctx)