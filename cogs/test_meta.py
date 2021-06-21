import pytest
from cogs import dotastats
import pytest

def test_meta(): 
  print('stuff' + dotastats.get_meta())
  assert True