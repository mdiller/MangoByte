from tracemalloc import start
from typing import List
import disnake

# mainly inspired from https://github.com/DisnakeDev/disnake/blob/187cd0c9461c74f9abcd1722709c0d794a21ba8f/examples/views/button/paginator.py

class Paginator(disnake.ui.View):
	def __init__(self, inter: disnake.CmdInter, embed_func, data, title: str, pages: int, start_page: int = 1, more_pages: bool = False):
		super().__init__(timeout=30)
		self.inter = inter
		self.title = title
		self.embed_func = embed_func
		self.data = data
		self.current_page = start_page
		self.total_pages = pages
		self.more_pages = more_pages
		if start_page == 1:
			self.prev_page.disabled = True
		if start_page == pages:
			self.next_page.disabled = True
	
	async def get_page_embed(self, page):
		embed = await self.embed_func(page, self.data)
		embed.title = self.title
		footer = f"Page {page}/{self.total_pages}"
		if self.more_pages:
			footer += "*"
		embed.set_footer(text=footer)
		return embed
	
	async def on_timeout(self):
		self.next_page.disabled = True
		self.prev_page.disabled = True
		await self.inter.edit_original_message(view=self)

	@disnake.ui.button(emoji="👈", style=disnake.ButtonStyle.secondary)
	async def prev_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
		self.current_page -= 1

		self.next_page.disabled = False
		if self.current_page == 0:
			self.prev_page.disabled = True
		embed = await self.get_page_embed(self.current_page)
		await interaction.response.edit_message(embed=embed, view=self)
	
	@disnake.ui.button(emoji="👉", style=disnake.ButtonStyle.secondary)
	async def next_page(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
		self.current_page += 1

		self.prev_page.disabled = False
		if self.current_page == self.total_pages:
			self.next_page.disabled = True
		embed = await self.get_page_embed(self.current_page)
		await interaction.response.edit_message(embed=embed, view=self)
