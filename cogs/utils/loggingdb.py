from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os
import re

Base = declarative_base()

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

# inserters

def insert_message(msg, cmd, session):
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

	session.add(message)
	session.commit()
	return message

def insert_command(ctx, session):
	command = Command()
	command.message_id = ctx.message.id
	command.command = ctx.command.name
	command.invoke_time = datetime.datetime.utcnow()
	command.status = "started"

	session.add(command)
	session.commit()
	return command

def command_finished(ctx, status, error, session):
	command = session.query(Command).filter_by(message_id=ctx.message.id).filter_by(command=ctx.command.name).first()
	command.status = status
	command.finish_time = datetime.datetime.utcnow()
	if error:
		command.error = error

	session.commit()

def insert_error(message, the_error, trace, session):
	error = Error()
	error.message_id = message.id
	error.timestamp = datetime.datetime.utcnow()
	error.command_error = type(the_error).__name__
	error.error = str(the_error)
	error.traceback = trace

	session.add(error)
	session.commit()
	return error

def insert_http_request(url, status, was_cached, cached, session):
	request = HttpRequest()

	request.url = url
	request.timestamp = datetime.datetime.utcnow()
	request.status = status
	request.was_cached = was_cached
	request.cached = cached

	session.add(request)
	session.commit()
	return request

# returns an open dotabase session
# if recreate is true, deletes any existing database first
def create_session(loggingdb_path):
	engine = create_engine('sqlite:///' + loggingdb_path)
	Base.metadata.create_all(engine)
	Session = sessionmaker(bind=engine)
	return Session()

# to call from mangobyte.py:
# loggingdb.update_commands_column(loggingdb_session, bot)
def update_commands_column(session, bot):
	for message in session.query(Message):
		match = re.search(r"^\?([^\s]+)(\s|$)", message.content, re.IGNORECASE)
		if match:
			cmd = bot.all_commands.get(match.group(1))
			if cmd:
				message.command = cmd.name
	session.commit()
	print("done updating logged commands!")