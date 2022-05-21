import datetime
import sys

import disnake
from disnake.ext import commands

import utils.other.errorhandling as errorhandling
import utils.other.initialization as initialization
import utils.other.update_script as update_script
from utils.tools.globals import botdata, logger, settings, httpgetter
from utils.tools.helpers import *

startupTimer = SimpleTimer()

description = """A discord bot built primarily around playing audio clips and dota related commands.
				For more information about me, try `/bot info`"""

bot = commands.AutoShardedBot(
	command_prefix=botdata.command_prefix_botmessage, 
	description=description, 
	case_insensitive=True,
	shard_count=settings.shard_count,
	sync_commands_debug=False,
	test_guilds=settings.test_guilds,
	reload=False)
bot.remove_command("help")


# registering some global events
@bot.event
async def on_shard_ready(shard_id):
	logger.info(f"shard {shard_id} ({len(bot.shards)} total) called its on_shard_ready ({len(bot.guilds)} guilds)")

just_run_update_script = False
initialize_started = False
@bot.event
async def on_ready():
	if just_run_update_script:
		await update_script.update(bot)
		await bot.close()
		return

	logger.info(f"on_ready() started")
	global initialize_started
	
	if not initialize_started:
		initialize_started = True
		await initialization.initialize(bot, startupTimer)
	else:
		logger.info("on_ready called again")

@bot.application_command_check()
def check_app_commands(inter: disnake.Interaction):
	return bot.get_cog("Admin").bot_check(inter)

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
	await errorhandling.on_prefix_command_error(ctx, error)

@bot.event
async def on_slash_command_error(inter: disnake.Interaction, error: commands.CommandError):
	await errorhandling.on_app_command_error(inter, error)


from cogs.admin import Admin
from cogs.audio import Audio
from cogs.dotabase import Dotabase
from cogs.dotastats import DotaStats
from cogs.general import General
from cogs.owner import Owner
from cogs.pokemon import Pokemon

if __name__ == '__main__':
	bot.add_cog(General(bot))
	bot.add_cog(Audio(bot))
	bot.add_cog(Dotabase(bot))
	bot.add_cog(DotaStats(bot))
	bot.add_cog(Pokemon(bot))
	bot.add_cog(Admin(bot))
	bot.add_cog(Owner(bot))

	if len(sys.argv) > 1 and sys.argv[1] in ["commands", "update"]:
		# instead of running the bot, run our script to update static files
		logger.disabled = True
		just_run_update_script = True
		print("Starting bot temporarily...")
		loop = asyncio.get_event_loop()
		loop.run_until_complete(bot.start(settings.token))
	else:
		logger.event("startup", {
			"message": "mangobyte script started"
		})
		logger.info(f"Starting mango at {datetime.datetime.today().strftime('%d-%b-%Y %I:%M %p')}")
		bot.run(settings.token)


