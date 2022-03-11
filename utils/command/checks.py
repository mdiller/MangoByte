import disnake
from disnake.ext import commands
from utils.tools.globals import botdata
from utils.tools.helpers import InterContext

#
# This is a "heavily" modified version of checks.py, originally made by Rapptz
#
#                 https://github.com/Rapptz
#          https://github.com/Rapptz/RoboDanny/tree/async
#

def is_owner_check(author):
	return author.id == 152151513232310272

def is_owner():
	return commands.check(lambda ctx_inter: is_owner_check(ctx_inter.author))

def is_admin_check(ctx_inter: InterContext, user=None):
	channel = ctx_inter.channel
	if user is None:
		user = ctx_inter.author
	if is_owner_check(user):
		return True
	if isinstance(channel, disnake.abc.PrivateChannel):
		return False # All admin commands should be guild specific and not work on PM channels
	admin_role_id = botdata.guildinfo(ctx_inter.guild).botadmin
	if admin_role_id:
		for role in user.roles:
			if role.id == admin_role_id:
				return True

	perms = channel.permissions_for(user)
	return perms.administrator

def is_admin():
	return commands.check(lambda ctx_inter: is_admin_check(ctx_inter))

def is_not_PM():
	return commands.check(lambda ctx_inter: not isinstance(ctx_inter.channel, disnake.abc.PrivateChannel))
