""" A collection of functions for RSS feed parsing"""

import discord
from dateutil import parser
import regex as re
from __main__ import botdata
from bs4 import BeautifulSoup

    
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
