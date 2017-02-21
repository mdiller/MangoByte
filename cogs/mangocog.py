from __main__ import settings
from cogs.utils.helpers import *
from cogs.utils.clip import *



class MangoCog:
	def __init__(self, bot):
		self.bot = bot

	async def get_clip_try_types(self, clipid, trytypes=""):
		trytypes = trytypes.split("|")
		try:
			return await self.get_clip(clipid)
		except MissingClipType:
			while len(trytypes) > 0:
				try:
					return await self.get_clip("{}:{}".format(trytypes.pop(), clipid))
				except ClipNotFound:
					continue
		raise MissingClipType(clipid)

	async def get_clip(self, clipid):
		cliptypes = Clip.types_dict()

		match = re.search("^(" + "|".join(cliptypes) + "):(.*)$", clipid)

		if not match:
			raise MissingClipType(clipid)

		return cliptypes[match.group(1)](match.group(2), self.bot)


	async def play_clip(self, clip, server=None):
		if isinstance(clip, str):
			clip = await self.get_clip(clip)

		audio = self.bot.get_cog("Audio")
		await (await audio.audioplayer(server)).queue_clip(clip)