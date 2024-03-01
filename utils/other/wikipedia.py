import re

from bs4 import BeautifulSoup, Tag
from utils.tools.globals import httpgetter
from utils.tools.helpers import *


def tagsToMarkdown(tag, plaintext=False):
	if isinstance(tag, list):
		result = ""
		for i in tag:
			result += tagsToMarkdown(i, plaintext)
		return result
	elif isinstance(tag, str):
		return tag
	elif isinstance(tag, Tag):
		if plaintext:
			return tagsToMarkdown(tag.contents, plaintext)
		elif tag.name == "b":
			return f"**{tagsToMarkdown(tag.contents)}**"
		elif tag.name == "i":
			return f"*{tagsToMarkdown(tag.contents)}*"
		elif tag.name in [ "sub", "sup" ]:
			if "reference" in tag.get("class", []):
				return "" # dont include references
			text = tagsToMarkdown(tag.contents, plaintext=True)
			if len(text) and text[0] == "[" and text[-1] == "]":
				return "" # this is a references thing you cant fool me
			replacements = {} # self.subscripts if tag.name == "sub" else self.superscripts
			new_text = ""
			for c in text:
				new_text += replacements.get(c) if c in replacements else c
			return new_text
		elif tag.name == "a":
			if tag.get("href") is None:
				return tagsToMarkdown(tag.contents)
			if tag["href"].startswith("#"):
				return "" # dont include references
			href = re.sub("^/wiki/", "https://en.wikipedia.org/wiki/", tag['href'])
			href = re.sub("^//upload.wikimedia.org", "https://upload.wikimedia.org", href)
			href = re.sub(r"(\(|\))", r"\\\1", href)

			contents = tagsToMarkdown(tag.contents)
			if contents == "":
				return ""
			return f"[{contents}]({href})"
		elif tag.name in [ "style" ]:
			return ""
		else:
			# raise UserError(f"Unrecognized tag: {tag.name}")
			return tagsToMarkdown(tag.contents)
	
	return str(tag)


async def find_disambiguations(pageid):
	data = await httpgetter.get(f"{base_query}&prop=revisions&rvprop=content&rvparse&rvlimit=1&pageids={pageid}")
	html = data["query"]["pages"][str(pageid)]["revisions"][0]["*"]

	lis = BeautifulSoup(html, "html.parser").find_all('li')
	filtered_lis = [li for li in lis if not 'tocsection' in ''.join(li.get('class', []))]
	return [li.a.get_text() for li in filtered_lis if li.a]

async def retrieve_page_info(title_input):
	data = await httpgetter.get(f"{base_query}&list=search&srprop&srlimit=1&srinfo=suggestion&srsearch={title_input}")
	if len(data["query"]["search"]) == 0:
		raise UserError("Couldn't find anything for that")
	info = data["query"]["search"][0]
	title = info["title"]
	pageid = info["pageid"]
	data = await httpgetter.get(f"{base_query}&prop=info|pageprops&inprop=url&ppprop=disambiguation&redirects&pageids={pageid}")
	page_info = data["query"]["pages"][str(pageid)]
	if "pageprops" in page_info and "disambiguation" in page_info["pageprops"]:
		options = await find_disambiguations(pageid)
		if len(options) == 0 or options[0] == title or options[0] == title_input:
			raise UserError("Couldn't find anything for that")
		else:
			return await retrieve_page_info(options[0])
	return page_info


base_url = "https://en.wikipedia.org/w/api.php"

base_query = f"{base_url}?format=json&action=query"

class WikipediaPage():
	def __init__(self, page_info):
		self.page_info = page_info
		self.id = page_info["pageid"]
		self.title = page_info["title"]
		self.url = page_info["fullurl"]

	async def load_page_content(self):
		page_html = await httpgetter.get(self.url, "text")

		page_html = BeautifulSoup(page_html, "html.parser")
		page_html = page_html.find(id="mw-content-text")

		def findSummaryParagraph(tag):
			has_content = False
			for child in tag.contents:
				if child.name != "span" and str(child).strip() != "":
					has_content = True
			return tag.name == "p" and not tag.attrs and has_content

		summary_html = page_html.find("div").find(findSummaryParagraph, recursive=False)
		summary_html = summary_html.contents if summary_html is not None else ""

		summary = tagsToMarkdown(summary_html)
		def markdownLength(text):
			text = re.sub(r"\[([^\[]*)]\([^\(]*\)", r"\1", text)
			return len(text)

		# cut to length at the end of a sentance
		sentance_end_pattern = r"([^\s\.]+\.)(\s|$)"
		matches = re.finditer(sentance_end_pattern, summary)
		if matches:
			for match in list(matches):
				if markdownLength(summary[0:match.end()]) > 70:
					summary = summary[0:match.end()]
					break
		
		self.markdown = summary

		image_data = await httpgetter.get(f"{base_query}&generator=images&gimlimit=max&prop=imageinfo&iiprop=url&pageids={self.id}")
		images = []
		if "query" in image_data:
			for imageid, image in image_data["query"]["pages"].items():
				images.append(image["imageinfo"][0]["url"])

		for image in page_html.find_all(class_="navbox"):
			image.decompose()
		for image in page_html.find_all(class_="mbox-image"):
			image.decompose()
		for image in page_html.find_all(class_="metadata plainlinks stub"):
			image.decompose()

		page_html_text = page_html.prettify()

		best_image = None
		best_image_index = -1
		for image in images:
			if "Wikisource-logo" in image:
				continue
			if re.search(r"\.(png|jpg|jpeg|gif)$", image, re.IGNORECASE):
				index = page_html_text.find(image.split('/')[-1])
				if index != -1 and (best_image_index == -1 or index < best_image_index):
					best_image = image
					best_image_index = index
		self.image = best_image


async def get_wikipedia_page(name):
	page_info = await retrieve_page_info(name)
	page = WikipediaPage(page_info)
	await page.load_page_content()
	return page

