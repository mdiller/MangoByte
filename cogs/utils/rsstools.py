""" A collection of functions for RSS feed parsing"""

import discord
from dateutil import parser
import regex as re
from __main__ import botdata
import aiohttp
import asyncio
from bs4 import BeautifulSoup

async def get_html(url):
    """ Takes url, returns html. No error handling"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            return html


def has_new_dota(feed):
    """ Takes a feedparser feed for the dota 2 blog, checks to see if newest publish date is newer
    than what is on record. This requires looking at the botdata json field "blog_date"
    If it cannot find the field, will automatically return false
    returns boolean"""
    new = ""
    old = botdata.blog_date
    if feed.entries:
        new = feed.entries[0].published
    else:
        return False
    if old and new != "":
        if old != "":
            if parser.parse(new )>parser.parse(old):
                botdata.blog_date = new
                return True
            else:
                return False
        else:
            botdata.blog_date = new
            return False

    
def create_embed(blog_title, entry):
    """ Takes a blog title and feedparser entry, and returns a rich embed object linking to the post"""
    response = discord.Embed(type='rich')

    ### pull the hook from the entry html for introduction
    soup = BeautifulSoup(entry.content[0]['value'], "html.parser")
    first_paragraph = "" 
    for p in soup.find_all('p'): #find first paragraph of text
        if p.text != '':
            first_paragraph = p.text
            break
    sentence = re.split('(?<=[.!?]) +',first_paragraph) #split the paragraph into sentences
    hook = ""
    if len(sentence)< 2: #limit hook to first two senteces of that paragraph
        hook = first_paragraph
    else:
        hook = sentence[0]+' '+sentence[1]
            
    ###pull other data
    link = entry.link #pull link for newest blog
    published = parser.parse(entry.published) #date
    image=soup.find("img" )
    header = f'The {blog_title} has updated!'

    ###assign things to the embed object
    response.title = entry.title
    if image: #there may not be one
        response.set_image(url = image["src"])
        response.image.proxy_url=link
    response.timestamp = published
    response.add_field(name = header, value = hook , inline = False)
    response.url = link

    return response
