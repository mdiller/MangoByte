from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os

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

	def __repr__(self):
		return f"{self.author_name}: {self.clean_content}"


def convert_message(msg):
	message = Message()
	message.id = msg.id
	message.author_id = msg.author.id
	message.author_name = msg.author.name
	if msg.server:
		message.server_id = msg.server.id
	else:
		message.server_id = None
	message.channel_id = msg.channel.id
	message.timestamp = msg.timestamp
	message.content = msg.content
	message.clean_content = msg.clean_content
	message.mentions = "|".join(map(lambda u: u.id, msg.mentions))
	return message


# returns an open dotabase session
# if recreate is true, deletes any existing database first
def create_session(loggingdb_path):
	engine = create_engine('sqlite:///' + loggingdb_path)
	Base.metadata.create_all(engine)
	Session = sessionmaker(bind=engine)
	return Session()