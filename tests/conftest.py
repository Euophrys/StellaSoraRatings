import os

import pytest
from ssr.data import GameData, DEFAULT_DATA_ROOT
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

os.environ.setdefault("SSR_WORKERS", "1")   # tests simulate in-process; test_parallel.py turns the workers on


@pytest.fixture(scope="session")
def gd():
    return GameData(DEFAULT_DATA_ROOT)


@pytest.fixture(scope="session")
def team(gd):
    from ssr.team import load_team
    return load_team(gd, TEAMS / "fl_noya_skill.yaml")
