import datetime
import sys
from translator import translator
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

intents = disnake.Intents.default()
intents.message_content = True

bot = commands.AutoShardedBot(
	command_prefix="?", # for any lingering owner-only commands
	description=description, 
	case_insensitive=True,
	shard_count=settings.shard_count,
	sync_commands_debug=False,
	test_guilds=settings.test_guilds,
	reload=False,
	intents=intents)
bot.remove_command("help")

""""
When flag reaction gets added to the bot reply it translate the text based on the flag country
"""
@bot.event
async def on_reaction_add(reaction, user):
    
    supported_lang = ['🇮🇷','🇷🇺','🇩🇪','🇺🇸']
    message = reaction.message

    #refrence message means bot replied to user and user did not use / commands like /help
    if message.reference is not None:
        # get channel id where reaction was added 
        channel = bot.get_channel(message.channel.id)
        # fetch the message that reaction was added to it
        question_author_message = await channel.fetch_message(message.reference.message_id)
        if question_author_message.author.id == user.id and reaction.emoji in supported_lang :
            
            #gets the pure message
            user_message = str(message.content)
            # message goes to transtalor to be translated
            translate = translator.eng_translator(user_message,reaction.emoji)

            await message.edit(content=translate)
        else:
            await message.remove_reaction(reaction.emoji,user)	
	# intractiion means that user used / command like /help 
    elif message.interaction.type.name == 'application_command':
	
        channel = bot.get_channel(message.channel.id)
        question_author_message = await channel.fetch_message(message.id)

        if question_author_message.interaction.user.id == user.id and reaction.emoji in supported_lang :
    			
            embed_to_edit = question_author_message.embeds[0]  # Assuming there is only one embed in the message
          
            translate = translator.eng_translator(embed_to_edit.description,reaction.emoji)
            embed_to_edit.description = translate
            await question_author_message.edit(embed=embed_to_edit)

        else:
            await message.remove_reaction(reaction.emoji,user)	
	    
# registering some global events
@bot.event
async def on_shard_ready(shard_id):
	logger.info(f"shard {shard_id} ({len(bot.shards)} total) called its on_shard_ready ({len(bot.guilds)} guilds)")

@bot.event
async def on_ready():
	logger.info(f"on_ready() triggered")

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
		loop.create_task(update_script.update(bot))
		loop.run_until_complete(bot.start(settings.token))
	else:
		print(f"Starting mango at {datetime.datetime.today().strftime('%d-%b-%Y %I:%M %p')}")
		bot.loop.create_task(initialization.initialize(bot, startupTimer))
		bot.run(settings.token)


