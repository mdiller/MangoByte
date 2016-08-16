import discord
import asyncio
import string
from discord.ext import commands
from ctypes.util import find_library

# /1/17/Treant_move_20
# /3/3b/Troll_lose_03
# /1/10/Timb_rare_01
# /f/f1/Slark_rare_02
# /e/e0/Drag_inthebag_01
# /b/b7/Bristle_inthebag_01
# /9/9d/Undying_gummy_vit_01
# /b/b5/Undying_gummy_vit_03
# /a/af/Spir_move_26
# /4/43/Beas_ability_animalsound_05

discord.opus.load_opus(find_library('opus'))


class MangoCog:
	"""MangoByte: like a normal byte, but jucier"""

	def __init__(self, bot):
		self.bot = bot
		self.voice = None
		self.player = None
		self.voice_channel = None

	# whether or not the bot is currently talking
	async def is_talking(self):
		return (self.player is not None) and (not self.player.is_done())


	# try to say an mp3, and if we arent in a voice channel, join the default one
	async def try_talking(self, mp3name, author, volume=1.0):
		if(self.voice is None):
			if not isinstance(author, discord.Member):
				await bot.say("You gotta start me from a server man.")
				return
			if author.voice_channel is None:
				print("attempted to join channel None")
				bot.say("Plz join a voice channel so I know were to go")
				return
			try:
				self.voice = await self.bot.join_voice_channel(author.voice_channel)
			except discord.ClientException:
				print('already in a voice channel, but voice was null')
				return
			except discord.InvalidArgument:
				print('default channel was not a valid voice channel')
				return
			else:
				print('joined channel ' + author.voice_channel.name)
				self.voice_channel = author.voice_channel

		if await self.is_talking():
			# we have a player and its playing something
			print("interruption")
			await self.bot.say("I'm already talking, don't interrupt. rude.")
			return

		try:
			self.player = self.voice.create_ffmpeg_player(mp3name)
			self.player.volume = volume
			self.player.start()
		except Exception as e:
			print(str(e))
			await self.bot.say("thats not valid input, silly.")


	@commands.command(pass_context=True)
	async def ping(self, ctx, count : int):
		"""Pings a number of times(within reason)

		Pings... a number of times.... within reason. *glares at blanedale*"""
		if count < 1:
			await self.bot.say("thats not enough pings. stahp trying to break me.")
			return
		if count > 99:
			await self.bot.say("thats too many pings. stahp trying to break me.")
			return

		ping_string = ""
		for i in range(0, count):
			ping_string += "Ping "
		await self.bot.say(ping_string, tts=True)

	@commands.command(pass_context=True)
	async def dota(self, ctx, dota_response : str):
		"""Plays a dota response

		The format for input is the end of a dota2 gamepedia url.
		Some gooduns:
		?dota /1/17/Treant_move_20
		?dota /3/3b/Troll_lose_03
		?dota /1/10/Timb_rare_01
		?dota /f/f1/Slark_rare_02
		?dota /e/e0/Drag_inthebag_01
		?dota /b/b7/Bristle_inthebag_01
		?dota /9/9d/Undying_gummy_vit_01
		?dota /b/b5/Undying_gummy_vit_03
		?dota /a/af/Spir_move_26
		?dota /4/43/Beas_ability_animalsound_05

		Note: This command will eventually be improved substantial"""
		await self.try_talking('http://hydra-media.cursecdn.com/dota2.gamepedia.com' + dota_response + '.mp3', ctx.message.author, volume=0.3)

	@commands.command(pass_context=True)
	async def hello(self, ctx):
		"""Says hello

		WHAT MORE DO YOU NEED TO KNOW!?!?!? IS 'SAYS HELLO' NOT CLEAR ENOUGH FOR YOU!?!!11?!!?11!!?!??"""
		await self.try_talking('resource/hello.mp3', ctx.message.author)

	@commands.command(pass_context=True)
	async def play(self, ctx, filename : str):
		"""Plays a local mp3

		There will be a new command called playlist soon, which will list all of the available clips"""
		await self.try_talking('resource/' + filename + '.mp3', ctx.message.author)

	@commands.command(pass_context=True)
	async def playurl(self, ctx, url : str):
		"""Plays an mp3 file at a url

		Make sure to use http, not https.
		One way to use this is to go to:
		http://people.oregonstate.edu/~dillerm/ResponsePlayer/
		Once there, find a good audio clip, right click on it, select copy url address, and do the thing."""
		await self.try_talking(url, ctx.message.author)

	@commands.command(pass_context=True)
	async def echo(self, ctx, *, message : str):
		"""Echo...

		I would hurl words into this darkness and wait for an echo, and if an echo sounded, no matter how faintly, I would send other words to tell, to march, to fight, to create a sense of the hunger for life that gnaws in us all"""
		await bot.say(message)

	#function called when this event occurs
	async def on_voice_state_update(self, before, after):
		if self.voice_channel is None or after.voice_channel is None or before.voice_channel is not None:
			# if the bot or the member are not in a voice channel, don't worry about checking that theyre equal
			return
		if after.voice_channel.id == self.voice_channel.id:
			await asyncio.sleep(3)
			await self.try_talking('resource/hello.mp3', after)



bot = commands.Bot(command_prefix='?', description="""a bot that does stuff n things""")
cog = MangoCog(bot)
bot.add_cog(cog)

@bot.event
async def on_ready():
	print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))

@bot.event
async def on_voice_state_update(before, after):
	await cog.on_voice_state_update(before, after)
	

f = open('token.txt', 'r')
token = f.read()

bot.run(token)
