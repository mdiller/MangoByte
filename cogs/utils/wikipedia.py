from __main__ import settings, httpgetter
from bs4 import BeautifulSoup, Tag

# def oldfunc():
# 	try:
# 		if title == "random":
# 			return wikipedia.page(title=wikipedia.random(1), redirect=True, auto_suggest=True)
# 		return wikipedia.page(title=title, redirect=True, auto_suggest=True)
# 	except (wikipedia.exceptions.DisambiguationError, wikipedia.exceptions.PageError) as e:
# 		if title == "random":
# 			return getWikiPage(title)
# 		if isinstance(e, wikipedia.exceptions.PageError) or len(e.options) == 0:
# 			raise UserError(f"Couldn't find anythin' fer \"*{thing}*\"")
# 		if e.options[0] == title:
# 			raise UserError("Can't find things on wiki for that")
# 		return getWikiPage(e.options[0])


async def find_disambiguations(pageid):
	data = await httpgetter.get(f"{base_query}&prop=revisions&rvprop=content&rvparse&rvlimit=1&pageids={pageid}")
	html = data["query"]["pages"][str(pageid)]["revisions"][0]["*"]

	lis = BeautifulSoup(html, 'html.parser').find_all('li')
	filtered_lis = [li for li in lis if not 'tocsection' in ''.join(li.get('class', []))]
	return [li.a.get_text() for li in filtered_lis if li.a]

async def retrieve_page_info(title):
	data = await httpgetter.get(f"{base_query}&list=search&srprop&srlimit=1&srinfo=suggestion&srsearch={title}")
	info = data["query"]["search"][0]
	title = info["title"]
	pageid = info["pageid"]
	data = await httpgetter.get(f"{base_query}&prop=info|pageprops&inprop=url&ppprop=disambiguation&redirects&pageids={pageid}")
	page_info = data["query"]["pages"][str(pageid)]
	if "pageprops" in page_info and "disambiguation" in page_info["pageprops"]:
		options = await find_disambiguations(pageid)
		if len(options) == 0 or options[0] == title:
			raise UserError("Couldn't find anything for that")
		else:
			return await retrieve_page_info(options[0])
	return page_info


# &list=search&srprop&srlimit=1&limit=1&srinfo=suggestion&    srsearch=Experiment
# &prop=info|pageprops&inprop=url&ppprop=disambiguation&redirects&    titles=Experiment
# &generator=images&gimlimit=max&prop=imageinfo&iiprop=url&    titles=Experiment


# &list=search&srprop&srlimit=1&limit=1&srinfo=suggestion&    srsearch=test
# &prop=info|pageprops&inprop=url&ppprop=disambiguation&redirects&    titles=Test
# &prop=revisions&rvprop=content&rvparse&rvlimit=1&    titles=Test


base_url = "https://en.wikipedia.org/w/api.php"

base_query = f"{base_url}?format=json&action=query"

class WikipediaPage():
	def __init__(self, page_info):
		self.page_info = page_info
		self.id = page_info["pageid"]
		self.title = page_info["title"]
		self.url = page_info["fullurl"]

	async def load_images(self):
		data = await httpgetter.get(f"{base_query}&generator=images&gimlimit=max&prop=imageinfo&iiprop=url&pageids={self.id}")
		self.images = []
		for imageid, image in data["query"]["pages"].items():
			self.images.append(image["imageinfo"][0]["url"])


async def get_wikipedia_page(name):
	page_info = await retrieve_page_info(name)
	page = WikipediaPage(page_info)
	await page.load_images()
	return page

