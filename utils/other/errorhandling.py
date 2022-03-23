import json
import traceback
import typing

import disnake
from disnake.ext import commands
from utils.command.clip import *
from utils.command.commandargs import *
from utils.tools.globals import botdata, logger, loggingdb, settings
from utils.tools.helpers import *

# Note: This code used to be in mangobyte.py so look there for more history

with open(settings.resource("json/deprecated_commands.json"), "r") as f:
	deprecated_commands = json.loads(f.read())


async def get_cmd_signature(ctx):
	ctx.bot.help_command.context = ctx
	return ctx.bot.help_command.get_command_signature(ctx.command)

# Whether or not we report invalid commands
async def invalid_command_reporting(ctx):
	if ctx.message.guild is None:
		return True
	else:
		return botdata.guildinfo(ctx.message.guild.id).invalidcommands

async def on_prefix_command_error(ctx: commands.Context, error: commands.CommandError):
	bot: commands.Bot
	bot = ctx.bot
	cmdpfx = botdata.command_prefix(ctx)

	try:
		if isinstance(error, commands.CommandNotFound):
			cmd = ctx.message.content[1:].split(" ")[0]
			slash_command_names = list(map(lambda c: c.name, bot.help_command.expand_subcommands(bot.slash_commands)))
			if cmd in deprecated_commands:
				logger.info(f"deprecated command '{cmd}' attempted")
				if deprecated_commands[cmd].startswith("_"):
					await ctx.send(f"{cmdpfx}{cmd}` has been deprecated. {deprecated_commands[cmd][1:]}")
					return
				await ctx.send(f"`{cmdpfx}{cmd}` has been deprecated. Try `/{deprecated_commands[cmd]}` instead.")
				return
			elif cmd in slash_command_names:
				logger.info(f"deprecated command '{cmd}' attempted")
				await ctx.send(f"`{cmdpfx}{cmd}` has been moved to a slash command. Try typing `/{cmd}`.")
				return
			elif cmd == "" or cmd.startswith("?") or cmd.startswith("!"):
				return # These were probably not meant to be commands

			if cmd.lower() in bot.commands:
				new_message = ctx.message
				new_message.content = cmdpfx + cmd.lower() + ctx.message.content[len(cmd) + 1:]
				await bot.process_commands(new_message)
			elif await invalid_command_reporting(ctx):
				await ctx.send(f"🤔 Ya I dunno what a '{cmd}' is, but it ain't a command. Try `{cmdpfx}help` fer a list of things that ARE commands.")
		elif isinstance(error, CustomBadArgument):
			await error.user_error.send_self(ctx, botdata)
		elif isinstance(error, commands.BadArgument):
			signature = await get_cmd_signature(ctx)
			await ctx.send((
				"Thats the wrong type of argument for that command.\n\n"
				f"Ya gotta do it like this:\n`{signature}`\n\n"
				f"Try `{cmdpfx}help {ctx.command}` for a more detailed description of the command"))
		elif isinstance(error, commands.MissingRequiredArgument):
			help_command = bot.help_command.copy()
			help_command.context = ctx
			await help_command.command_callback(ctx, command=ctx.command.name)
		else:
			await command_error_handler(ctx, error)
	except disnake.errors.Forbidden:
		try:
			await ctx.author.send("Looks like I don't have permission to talk in that channel, sorry")
		except disnake.errors.Forbidden:
			logger.error(f"double forbidden for message {ctx.message.id}")

async def on_app_command_error(inter: disnake.Interaction, error: commands.CommandError):
	await command_error_handler(inter, error)

async def command_error_handler(ctx_inter: InterContext, error: commands.CommandError):
	bot: commands.AutoShardedBot
	bot = ctx_inter.bot

	cmd_log_data = {}
	if isinstance(ctx_inter, commands.Context):
		cmd_log_data["message_id"] = ctx_inter.message.id
		identifier = f"[prefix_command: {ctx_inter.message.id}]"
	else:
		cmd_log_data["inter_id"] = ctx_inter.id
		identifier = f"[interaction: {ctx_inter.id}]"
		
	logger.event("command_finished", cmd_log_data)

	try:
		if isinstance(error, commands.CheckFailure):
			emoji_dict = read_json(settings.resource("json/emoji.json"))
			command = None
			if isinstance(ctx_inter, disnake.ApplicationCommandInteraction):
				command = ctx_inter.application_command.qualified_name
			elif isinstance(ctx_inter, commands.Context):
				command = ctx_inter.command

			emoji = None
			message = None
			if command and botdata.guildinfo(ctx_inter).is_disabled(command):
				emoji = bot.get_emoji(emoji_dict["command_disabled"])
				message = "This command is disabled for this guild"
			else:
				emoji = bot.get_emoji(emoji_dict["unauthorized"])
				message = "You're not authorized to run this command"
			
			if isinstance(ctx_inter, commands.Context):
				await ctx_inter.message.add_reaction(emoji)
			else:
				await ctx_inter.send(f"{emoji} {message}")
			return # The user does not have permissions
		elif isinstance(error, CustomBadArgument):
			await error.user_error.send_self(ctx_inter, botdata)
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, disnake.errors.Forbidden):
			await print_missing_perms(ctx_inter, error)
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, disnake.errors.HTTPException):
			await ctx_inter.send("Looks like there was a problem with discord just then. Try again in a bit.")
			logger.warning(f"discord http exception triggered {identifier}")
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, HttpError):
			await error.original.send_self(ctx_inter, botdata)
			if error.original.code != 404: # 404 errors are not worth reporting
				logger.warning(f"http error {error.original.code} on {identifier} for url: {error.original.url}")
			await loggingdb.command_finished(ctx_inter, "user_errored", error.original.message)
		elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, UserError):
			await error.original.send_self(ctx_inter, botdata)
			await loggingdb.command_finished(ctx_inter, "user_errored", error.original.message)
		elif isinstance(error, commands.ConversionError) and isinstance(error.original, UserError):
			await error.original.send_self(ctx_inter, botdata)
		elif isinstance(error, commands.ConversionError) and isinstance(error.original, CustomBadArgument):
			await error.original.user_error.send_self(ctx_inter, botdata)
		else:
			await ctx_inter.send("Uh-oh, sumthin dun gone wrong 😱")
			trace_string = await report_error(ctx_inter, error, skip_lines=4)
			if settings.debug:
				if len(trace_string) > 1950:
					trace_string = "TRACETOOBIG:" + trace_string[len(trace_string) - 1950:]
				await ctx_inter.send(f"```{trace_string}```")
	except disnake.errors.Forbidden:
		try:
			await ctx_inter.author.send("Looks like I don't have permission to talk in that channel, sorry")
		except disnake.errors.Forbidden:
			pass
	except Exception as e:
		logging.error(f"uncaught error {e} when processing CommandError")
		await report_error(ctx_inter, e, skip_lines=0)

error_file = "errors.json"

async def print_missing_perms(ctx_inter: InterContext, error):
	if not (ctx_inter.guild):
		await ctx_inter.send("Uh-oh, sumthin dun gone wrong 😱")
		trace_string = await report_error(ctx_inter, error, skip_lines=0)
	my_perms = ctx_inter.channel.permissions_for(ctx_inter.guild.me)
	perms_strings = read_json(settings.resource("json/permissions.json"))
	perms = []
	for i in range(0, 32):
		if ((settings.permissions >> i) & 1) and not ((settings.permissions >> i) & 1):
			words = perms_strings["0x{:08x}".format(1 << i)].split("_")
			for i in range(0, len(words)):
				words[i] = f"**{words[i][0] + words[i][1:].lower()}**"
			perms.append(" ".join(words))
	if perms:
		await ctx_inter.send("Looks like I'm missin' these permissions 😢:\n" + "\n".join(perms))
	else:
		await ctx_inter.send(f"Looks like I'm missing permissions 😢. Have an admin giff me back my permissions, or re-invite me to the server using this invite link: {settings.invite_link}")


async def report_error(ctx_inter_msg: typing.Union[InterContext, disnake.Message], error, skip_lines=2):
	try:
		if isinstance(error, disnake.errors.InteractionTimedOut):
			trace = [ "InteractionTimedOut: took longer than 3 seconds" ]
		else:
			if hasattr(error, "original"):
				raise error.original
			else:
				raise error
	except:
		trace = traceback.format_exc().replace("\"", "'").split("\n")
		if skip_lines > 0 and len(trace) >= (2 + skip_lines):
			del trace[1:(skip_lines + 1)]
		trace = [x for x in trace if x] # removes empty lines

	trace_string = "\n".join(trace)

	if isinstance(ctx_inter_msg, commands.Context):
		message = ctx_inter_msg.message
		await loggingdb.insert_error(message, error, trace_string)
		logger.error(f"Error on: {message.content}\nMessage Id: {message.id}\nAuthor Id: {message.author.id}\n{trace_string}\n")
	elif isinstance(ctx_inter_msg, disnake.Interaction):
		logger.error(f"Error on: {stringify_slash_command(ctx_inter_msg)}\ninter_id: {ctx_inter_msg.id}\nauthor_id: {ctx_inter_msg.author.id}\n{trace_string}\n")
	else: # is a message
		message = ctx_inter_msg
		await loggingdb.insert_error(message, error, trace_string)
		logger.error(f"Error on: {message.content}\nmessage_id: {message.id}\nauthor_id: {message.author.id}\n{trace_string}\n")
	return trace_string
