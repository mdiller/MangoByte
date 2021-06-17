import pytest
import mangobyte
import mock
import asyncio
from pprint import pprint
from cogs import dotastats

@pytest.mark.asyncio
async def test_get_meta_json(): 
	stats = dotastats.DotaStats(mock.Mock())
	meta_return = await stats.get_meta_json()
	# pprint(meta_return)
	assert True

@pytest.mark.asyncio
async def test_sort_meta(): 
	stats = dotastats.DotaStats(mock.Mock())
	meta_return = await stats.get_meta_json()
	pprint(stats.sort_meta(meta_return))

	assert True
