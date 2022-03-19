import disnake
from utils.command.clip import *
from utils.tools.globals import botdata, logger, settings
from utils.tools.helpers import *

emoji_dict = read_json(settings.resource("json/emoji.json"))

def simple_get_emoji(key, bot):
	emoji_id = emoji_dict.get(key)
	if emoji_id is None:
		return f":{key}:"
	emoji = bot.get_emoji(emoji_id)
	if emoji is None:
		return f"<:{key}:{emoji_id}>"
	return str(emoji)


class MangoCog(disnake.ext.commands.Cog):
	bot: commands.AutoShardedBot

	def __init__(self, bot):
		self.bot = bot

	def get_emoji(self, key):
		return simple_get_emoji(key, self.bot)

	@property
	def name(self):
		return self.__class__.__name__

	async def send_owner(self, *args, **kwargs):
		appinfo = await self.bot.application_info()
		await appinfo.owner.send(*args, **kwargs)

	async def get_clip_try_types(self, clipid, trytypes, ctx_inter: InterContext):
		trytypes = trytypes.split("|")
		try:
			return await self.get_clip(clipid, ctx_inter)
		except MissingClipType:
			while len(trytypes) > 0:
				try:
					return await self.get_clip("{}:{}".format(trytypes.pop(), clipid), ctx_inter)
				except ClipNotFound:
					continue
		raise MissingClipType(clipid)

	async def get_clip(self, clipid, ctx_inter: InterContext):
		cliptypes = Clip.types_dict()

		match = re.search(f"^({'|'.join(cliptypes)}):(.*)$", clipid.replace("\n", " "))

		if not match:
			raise MissingClipType(clipid)

		return await cliptypes[match.group(1)]().init(match.group(2), self.bot, ctx_inter)


	async def play_clip(self, clip, ctx_inter: InterContext):
		if isinstance(clip, str):
			clip = await self.get_clip(clip, ctx_inter)

		audio = self.bot.get_cog("Audio")

		audioplayer = await audio.audioplayer(ctx_inter)
		audio.last_played_audio[audioplayer.guild_id] = datetime.datetime.now()
		await audioplayer.queue_clip(clip, ctx_inter)

	def cmdpfx(self, ctx):
		return botdata.command_prefix(ctx)
