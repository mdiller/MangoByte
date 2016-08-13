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

discord.opus.load_opus(find_library('opus'))

description = '''a bot that does stuff n things.'''

bot = commands.Bot(command_prefix='?', description=description)

voice = None
    

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

@bot.command(pass_context=True)
async def ping(ctx, count : int):
    """Pings a number of times."""
    ping_string = ""
    for i in range(0, count):
        ping_string += "Ping "
    await bot.send_message(ctx.message.channel, ping_string, tts=True)

@bot.command(pass_context=True)
async def play(ctx, dota_response):
    """Plays a dota response."""
    global voice

    if voice is None:
        voice_channel = ctx.message.channel
        for c in list(ctx.message.channel.server.channels):
            if(c.name == 'General'):
                voice_channel = c
        voice = await bot.join_voice_channel(voice_channel)

    try:
        player = voice.create_ffmpeg_player('http://hydra-media.cursecdn.com/dota2.gamepedia.com' + dota_response + '.mp3')
        # dota mp3s are very loud, so make quieter
        player.volume = 0.30
        player.start()
    except Exception as e:
        print(str(e))
        await bot.send_message(ctx.message.channel, "invalid input")

@bot.command(pass_context=True)
async def hello(ctx):
    """Says hello."""
    global voice

    if voice is None:
        voice_channel = ctx.message.channel
        for c in list(ctx.message.channel.server.channels):
            if(c.name == 'General'):
                voice_channel = c
        voice = await bot.join_voice_channel(voice_channel)

    try:
        player = voice.create_ffmpeg_player('resource/hello.mp3')
        player.start()
    except Exception as e:
        print(str(e))
        await bot.send_message(ctx.message.channel, "error occured")
    

f = open('token.txt', 'r')

bot.run(f.read())
