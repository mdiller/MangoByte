from __main__ import settings, botdata, loggingdb_session
from cogs.utils.helpers import *
from cogs.utils.clip import *
import discord

emoji_dict = read_json(settings.resource("json/emoji.json"))

def simple_get_emoji(key, bot):
	emoji_id = emoji_dict.get(key)
	if emoji_id is None:
		return f":{key}:"
	emoji = bot.get_emoji(emoji_id)
	if emoji is None:
		return f"<:{key}:{emoji_id}>"
	return str(emoji)


class MangoCog(discord.ext.commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	def get_emoji(self, key):
		return simple_get_emoji(key, self.bot)

	@property
	def name(self):
		return self.__class__.__name__

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

		return await cliptypes[match.group(1)]().init(match.group(2), self.bot, ctx)


	async def play_clip(self, clip, ctx):
		if isinstance(clip, str):
			clip = await self.get_clip(clip, ctx)

		audio = self.bot.get_cog("Audio")
		await (await audio.audioplayer(ctx)).queue_clip(clip, ctx)

	def cmdpfx(self, ctx):
		return botdata.command_prefix(ctx)