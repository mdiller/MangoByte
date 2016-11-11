from discord.ext import commands

#
# This is a "heavily" modified version of checks.py, originally made by Rapptz
#
#                 https://github.com/Rapptz
#          https://github.com/Rapptz/RoboDanny/tree/async
#

async def is_owner_check(ctx):
	appinfo = await ctx.bot.application_info()
	return ctx.message.author.id == appinfo.owner.id

def is_owner():
	return commands.check(is_owner_check)
