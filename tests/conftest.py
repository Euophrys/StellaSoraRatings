import pytest
from ssr.data import GameData, DEFAULT_DATA_ROOT


@pytest.fixture(scope="session")
def gd():
    return GameData(DEFAULT_DATA_ROOT)
