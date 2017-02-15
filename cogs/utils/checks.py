from discord.ext import commands
from __main__ import botdata

#
# This is a "heavily" modified version of checks.py, originally made by Rapptz
#
#                 https://github.com/Rapptz
#          https://github.com/Rapptz/RoboDanny/tree/async
#

# This has problems because this cant be async but we need it to be to get appinfo
async def is_owner_check(ctx):
	appinfo = await ctx.bot.application_info()
	return ctx.message.author.id == appinfo.owner.id

def is_owner():
	return commands.check(is_owner_check)


async def isnt_banned(ctx):
	user_id = ctx.message.author.id
	return not botdata.userinfo(user_id).banned

def isnt_banned():
	return commands.check(is_owner_check)
