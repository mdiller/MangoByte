import asyncio
import datetime
import traceback

import disnake
from cogs.audio import Audio
from disnake.ext import commands
from utils.command.clip import *
from utils.command.commandargs import *
from utils.tools.botdata import GuildInfo
from utils.tools.globals import botdata, logger, loggingdb, settings
from utils.tools.helpers import *

# Note: This code used to be in mangobyte.py so look there for more history

async def initialize(bot: commands.Bot, startupTimer: SimpleTimer):
	try:
		logger.event("startup", {
			"message": "initialize started"
		})
		logger.info("Logged in as:\n{0} (ID: {0.id})".format(bot.user))
		logger.info("Connecting to voice channels if specified in botdata.json ...")

		bot.help_command.cog = bot.get_cog("General")
		appinfo = await bot.application_info()
		general_cog = bot.get_cog("General")
		audio_cog = bot.get_cog("Audio")
		initTimer = SimpleTimer()
		
		activity = disnake.Activity(
			name="restarting...",
			type=disnake.ActivityType.playing,
			start=datetime.datetime.utcnow())
		await bot.change_presence(status=disnake.Status.dnd, activity=activity)

		periodic_tasks = []
		if not settings.debug:
			periodic_tasks.append(audio_cog.voice_channel_culler)
		if settings.topgg:
			periodic_tasks.append(general_cog.update_topgg)
		if settings.infodump_path:
			periodic_tasks.append(general_cog.do_infodump)
		for task in periodic_tasks:
			if (not task.is_running()):
				task.start()

		# now do voice channels and the rest!
		minimum_channels_to_space = 50
		voice_channels_per_minute_timing = 4
		voice_channel_count = 0
		for guildinfo in botdata.guildinfo_list():
			if guildinfo.voicechannel is not None:
				voice_channel_count += 1
		expected_minutes = int(round(voice_channel_count / voice_channels_per_minute_timing))
		expected_finish = (datetime.datetime.now() + datetime.timedelta(minutes=expected_minutes)).strftime('%I:%M %p')
		if expected_finish[0] == "0":
			expected_finish = expected_finish[1:]
		should_space_connects =  voice_channel_count > minimum_channels_to_space
		message = "__**Initialization Started**__\n"
		if should_space_connects:
			message += f"{voice_channel_count} voice channels to connect, should take about {expected_minutes} minutes and finish around {expected_finish}"
		logger.info(message)
		if not settings.debug:
			await appinfo.owner.send(message)

		# trigger the actual voice channel reconnecting
		audio_cog = bot.get_cog("Audio")
		channel_tasks = []
		for guildinfo in botdata.guildinfo_list():
			if guildinfo.voicechannel is not None:
				task = asyncio.create_task(initial_channel_connect_wrapper(audio_cog, guildinfo))
				channel_tasks.append(task)
				if should_space_connects:
					await asyncio.sleep(int(60 / voice_channels_per_minute_timing))
		channel_connector = AsyncBundler(channel_tasks)
		await channel_connector.wait()
	except Exception as e:
		logger.error(traceback.format_exc())
	finally:
		if "TimeoutError" in channel_connector.exceptions_dict:
			seconds_to_wait = 60 * 10
			logger.error(f"there was a timeout error during initialization, waiting {seconds_to_wait} seconds before finishing")
			await asyncio.sleep(seconds_to_wait)

		logger.info("updating guilds")
		await loggingdb.update_guilds(bot.guilds)

		message = "__**Initialization Complete:**__\n"
		message += channel_connector.status_as_string("voice channels connected") + "\n\n"
		message += f"initialization took {initTimer}" + "\n"
		message += f"Full startup took {startupTimer}"

		logger.info(message + "\n")
		if not settings.debug:
			await appinfo.owner.send(message)

		game = disnake.Activity(
			name="DOTA 3 [?help]",
			type=disnake.ActivityType.playing,
			start=datetime.datetime.utcnow())
		await bot.change_presence(status=disnake.Status.online, activity=game)
		
		logger.event("startup", {
			"message": "initialize finished"
		})


async def initial_channel_connect_wrapper(audio_cog: Audio, guildinfo: GuildInfo):
	channel_id = guildinfo.voicechannel
	server_id = guildinfo.id
	logger.info(f"connecting voice to: {channel_id}")
	await initial_channel_connect(audio_cog, guildinfo)
	logger.info(f"connected: {channel_id}")


# returns 0 on successful connect, 1 on not found, and 2 on timeout, 3 on error
async def initial_channel_connect(audio_cog: Audio, guildinfo: GuildInfo):
	channel_id = guildinfo.voicechannel
	status = "connected"
	try:
		connect_task = audio_cog.connect_voice(guildinfo.voicechannel)
		await asyncio.wait_for(connect_task, timeout=200)
		return "connected"
	except UserError as e:
		if e.message == "channel not found":
			guildinfo.voicechannel = None
			raise
		else:
			logger.info(f"weird usererror on connection to channel '{channel_id}': {e.message}")
			raise
	except asyncio.TimeoutError:
		guildinfo.voicechannel = None
		raise
	except Exception as e:
		logger.error(f"exception thrown on connection to channel ({channel_id}): {str(e)}")
		guildinfo.voicechannel = None
		trace = traceback.format_exc().replace("\"", "'").split("\n")
		trace = [x for x in trace if x] # removes empty lines
		trace_string = "\n".join(trace) + "\n"
		logger.error(trace_string)
		raise
