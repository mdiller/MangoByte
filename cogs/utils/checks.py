import discord
from discord.ext import commands
from __main__ import botdata

#
# This is a "heavily" modified version of checks.py, originally made by Rapptz
#
#                 https://github.com/Rapptz
#          https://github.com/Rapptz/RoboDanny/tree/async
#

def is_owner_check(author):
	return author.id == 152151513232310272

def is_owner():
	return commands.check(lambda ctx: is_owner_check(ctx.message.author))

def is_admin_check(channel, author):
	if isinstance(channel, discord.abc.PrivateChannel):
		return False # All admin commands should be guild specific and not work on PM channels
	if is_owner_check(author):
		return True
	
	perms = channel.permissions_for(author)
	return perms.administrator

def is_admin():
	return commands.check(lambda ctx: is_admin_check(ctx.message.channel, ctx.message.author))

def is_not_PM():
	return commands.check(lambda ctx: not isinstance(ctx.message.channel, discord.abc.PrivateChannel))
