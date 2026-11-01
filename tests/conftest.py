import pytest
from ssr.data import GameData, DEFAULT_DATA_ROOT


@pytest.fixture(scope="session")
def gd():
    return GameData(DEFAULT_DATA_ROOT)


@pytest.fixture(scope="session")
def team(gd):
    from ssr.team import load_team, TEAMS
    return load_team(gd, TEAMS / "fl_noya_skill.yaml")
