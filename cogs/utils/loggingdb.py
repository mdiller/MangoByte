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

	command = Column(String)

	def __repr__(self):
		return f"{self.author_name}: {self.clean_content}"


def convert_message(ctx):
	msg = ctx.message
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
	if ctx.command:
		message.command = ctx.command.name
	return message

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