from __main__ import settings
from numpy import isin
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import sessionmaker, relationship
import sqlalchemy
from databases import Database, DatabaseURL
import asyncio
import disnake
from disnake.ext import commands
import datetime
import os
import re
import logging

from cogs.utils.helpers import InterContext
logger = logging.getLogger("mangologger")

Base = declarative_base()

def message_to_embed(message, cog):
	if message:
		return message.to_embed(cog)
	else:
		return disnake.Embed(description="None")


class Message(Base):
	__tablename__ = 'messages'

	id = Column(Integer, primary_key=True)
	author_id = Column(Integer)
	server_id = Column(Integer)
	channel_id = Column(Integer)

	timestamp = Column(DateTime)
	content = Column(String)
	clean_content = Column(String)
	author_name = Column(String)
	mentions = Column(String)

	command = Column(String) # keeping for legacy

	def to_embed(self, cog):
		embed = disnake.Embed(description=self.content)

		author = cog.bot.get_user(self.author_id)
		if author is not None:
			embed.set_author(name=f"{author.name} ({author.id})", icon_url=author.avatar.url)
		else:
			embed.set_author(name=self.author_id)

		embed.timestamp = self.timestamp
		embed.set_footer(text=self.id)

		return embed

	def __repr__(self):
		return f"{self.author_name}: {self.clean_content}"


class Command(Base):
	__tablename__ = 'commands'

	id = Column(Integer, primary_key=True) # auto-incrementing
	message_id = Column(Integer, ForeignKey("messages.id")) # the message it was called for
	command = Column(String)
	invoke_time = Column(DateTime)
	finish_time = Column(DateTime)
	error = Column(String) # the UserError if one ended the command, or the name of the discord error if that caused it
	status = Column(String)

	message = relationship("Message")

	def to_embed(self, cog):
		embed = message_to_embed(self.message, cog)

		if self.invoke_time is not None and self.finish_time is not None:
			embed.add_field(name="Duration", value=f"{(self.finish_time - self.invoke_time).total_seconds():.2f}")

		if self.status != "completed":
			if self.status == "user_errored":
				embed.add_field(name="UserError", value=self.error)
			else:
				embed.add_field(name="Status", value=self.status)
				if self.error:
					embed.add_field(name="Error", value=self.error)
					embed.color = disnake.Color.red()

		return embed

class HttpRequest(Base):
	__tablename__ = 'httprequests'

	id = Column(Integer, primary_key=True) # auto-incrementing
	url = Column(String)
	timestamp = Column(DateTime)
	status = Column(Integer) # http status code
	was_cached = Column(Boolean) # whether or not the result was already cached
	cached = Column(Boolean) # whether or not we cached the result


class Error(Base):
	__tablename__ = 'errors'

	id = Column(Integer, primary_key=True)
	message_id = Column(Integer, ForeignKey("messages.id"))
	timestamp = Column(DateTime)
	command_error = Column(String)
	error = Column(String)
	traceback = Column(String)

	message = relationship("Message")

	def error_text_chunks(self):
		maxlength = 1900
		result = f"{self.error}\n\n{self.traceback}"

		chunks = []
		thischunk = None
		for line in result.split("\n"):
			if thischunk is None:
				thischunk = line
			elif len(thischunk + line) > maxlength:
				chunks.append(f"```\n{thischunk}\n```")
				thischunk = line
			else:
				thischunk += "\n" + line
		if thischunk:
			chunks.append(f"```\n{thischunk}\n```")

		return chunks

	def to_embed(self, cog):
		embed = message_to_embed(self.message, cog)
		embed.color = disnake.Color.red()

		embed.timestamp = self.timestamp

		if self.command_error != "CommandInvokeError":
			embed.add_field(name="Error", value=self.command_error)

		return embed

class Guild(Base):
	__tablename__ = 'guilds'

	id = Column(Integer, primary_key=True)
	name = Column(String)
	join_time = Column(DateTime)
	leave_time = Column(DateTime)


def row2dict(row):
	d = {}
	for column in row.__table__.columns:
		d[column.name] = getattr(row, column.name)
	return d

# inserters

def print_debug(text):
	if True or settings.debug:
		logger.info(text)

class LoggingDb():
	def __init__(self, loggingdb_path):
		url = f"sqlite:///{loggingdb_path}"
		self.database_url = DatabaseURL(url)
		engine = sqlalchemy.create_engine(url)
		Base.metadata.create_all(engine)
		Session = sessionmaker(bind=engine)
		self.session = Session()
		self.loop = asyncio.get_event_loop()
		self.lock = asyncio.Lock(loop=self.loop)

	async def query_multiple(self, queries):
		async with self.lock, Database(self.database_url) as database:
			queries = map(lambda q: database.fetch_all(query=q), queries)
			return await asyncio.gather(*queries)

	async def query(self, query):
		async with self.lock, Database(self.database_url) as database:
			return await database.fetch_all(query=query)

	async def insert_row(self, database, table, row):
		await database.execute(query=table.__table__.insert().values(row2dict(row)))

	async def insert_message(self, msg, cmd):
		start_time = datetime.datetime.now()
		async with self.lock, Database(self.database_url) as database:
			message = Message()
			message.id = msg.id
			message.author_id = msg.author.id
			message.author_name = msg.author.name
			if msg.guild:
				message.server_id = msg.guild.id
			message.channel_id = msg.channel.id
			message.timestamp = msg.created_at
			message.content = msg.content
			message.clean_content = msg.clean_content
			message.mentions = "|".join(map(lambda u: str(u.id), msg.mentions))
			message.command = cmd

			await self.insert_row(database, Message, message)
			total_time = (datetime.datetime.now() - start_time).total_seconds()
			print_debug(f"insert_message(): {total_time * 1000:.2f}ms")
			return message

	async def insert_command(self, ctx):
		start_time = datetime.datetime.now()
		async with self.lock, Database(self.database_url) as database:
			command = Command()
			command.message_id = ctx.message.id
			command.command = ctx.command.name
			command.invoke_time = datetime.datetime.utcnow()
			command.status = "started"

			await self.insert_row(database, Command, command)
			total_time = (datetime.datetime.now() - start_time).total_seconds()
			print_debug(f"insert_command(): {total_time * 1000:.2f}ms")
			return command

	async def command_finished(self, ctx: InterContext, status, error):
		if not isinstance(ctx, commands.Context):
			return # just skip this if its not a context
		await asyncio.sleep(1)
		async with self.lock, Database(self.database_url) as database:
			start_time = datetime.datetime.now()
			if ctx.command is None:
				return
	
			cmd = self.session.query(Command).filter_by(message_id=ctx.message.id).order_by(sqlalchemy.desc(Command.id)).first()
			if not cmd:
				logger.info("couldnt find cmd to finish")
				return
	
			cmd.status = status
			cmd.finish_time = datetime.datetime.utcnow()
			self.session.commit()
	
			total_time = (datetime.datetime.now() - start_time).total_seconds()
			print_debug(f"command_finished(): {total_time * 1000:.2f}ms")

		# async with Database(self.database_url) as database:
			# if ctx.command is None:
			# 	return # no command to finish

			# values = {
			# 	"status": status,
			# 	"finish_time": datetime.datetime.utcnow()
			# }
			# if error:
			# 	values["error"] = error

			# cmdtable = Command.__table__
			# query = cmdtable.update().where(cmdtable.c.message_id==ctx.message.id).values(**values)
			# await database.execute(query=query)

	async def insert_error(self, message, the_error, trace):
		if not isinstance(message, disnake.Message):
			return # just skip this if its not a message
		start_time = datetime.datetime.now()
		async with self.lock, Database(self.database_url) as database:
			error = Error()
			error.message_id = message.id
			error.timestamp = datetime.datetime.utcnow()
			error.command_error = type(the_error).__name__
			error.error = str(the_error)
			error.traceback = trace

			await self.insert_row(database, Error, error)
			total_time = (datetime.datetime.now() - start_time).total_seconds()
			print_debug(f"insert_error(): {total_time * 1000:.2f}ms")
			return error

	async def insert_http_request(self, url, status, cached):
		start_time = datetime.datetime.now()
		async with self.lock, Database(self.database_url) as database:
			request = HttpRequest()

			request.url = url
			request.timestamp = datetime.datetime.utcnow()
			request.status = status
			request.was_cached = False
			request.cached = cached

			await self.insert_row(database, HttpRequest, request)
			total_time = (datetime.datetime.now() - start_time).total_seconds()
			print_debug(f"insert_http_request(): {total_time * 1000:.2f}ms")
			return request

	async def update_guilds(self, guilds):
		async with self.lock:
			guild_dict = {}
			for guild in guilds:
				guild_dict[guild.id] = guild

			# update existing guilds
			new_guild_ids = list(guild_dict.keys())
			for guild_log in self.session.query(Guild):
				if guild_log.id in new_guild_ids:
					new_guild_ids.remove(guild_log.id)

				if guild_log.leave_time is not None:
					guild_log.leave_time = None
				if guild_log.name == "<Unknown>":
					guild_log.name = guild.name

			# add new guilds
			for guild_id in new_guild_ids:
				guild = guild_dict[guild_id]
				guild_log = Guild()
				guild_log.id = guild.id
				guild_log.name = guild.name
				guild_log.join_time = guild.me.joined_at
				guild_log.leave_time = None
				self.session.add(guild_log)

			async with Database(self.database_url) as database:
				current_ids = ", ".join(list(map(lambda g: str(g), guild_dict.keys())))

				# fix all existing guilds that say they've left
				await database.execute(query=f"UPDATE guilds SET leave_time = NULL WHERE id in ({current_ids}) and leave_time is not NULL")

				# run query to remove guilds that have left
				await database.execute(query=f"UPDATE guilds SET leave_time = datetime('now','localtime') WHERE id not in ({current_ids}) and leave_time is NULL")
		self.session.commit()


	# only called manually
	def update_commands_column(self, bot):
		for message in self.session.query(Message):
			match = re.search(r"^\?([^\s]+)(\s|$)", message.content, re.IGNORECASE)
			if match:
				cmd = bot.all_commands.get(match.group(1))
				if cmd:
					message.command = cmd.name
		self.session.commit()
		logger.info("done updating logged commands!")

	# only called manually
	def add_missing_guilds(self, current_guilds):
		self.update_guilds(current_guilds, self.session)
		guilds = {}
		for message in self.session.query(Message).order_by(Message.timestamp):
			if message.server_id not in guilds:
				guilds[message.server_id] = {
					"first": message.timestamp,
					"last": message.timestamp
				}
			else:
				guilds[message.server_id]["last"] = message.timestamp

		for guild_id in guilds:
			found = False
			for guild in self.session.query(Guild):
				if str(guild.id) == str(guild_id):
					found = True
					break
			if not found:
				guild_log = Guild()
				guild_log.id = guild_id
				guild_log.name = "<Unknown>"
				guild_log.join_time = guilds[guild_id]["first"]
				guild_log.leave_time = guilds[guild_id]["last"]
				self.session.add(guild_log)
		self.session.commit()