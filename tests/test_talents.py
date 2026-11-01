"""Talents (dupes), `&once` events, and supports that trigger Marks (Shia)."""
from dataclasses import replace

import pytest

from ssr.data import GameData, REPO_ROOT
from ssr.game import talent_groups, talent_nodes
from ssr.sim import simulate
from ssr.team import Build, load_team


@pytest.fixture(scope="module")
def gd():
    return GameData()


@pytest.fixture(scope="module")
def shia_team(gd):
    return load_team(gd, REPO_ROOT / "teams" / "fl_noya_t1_shia_tilia.yaml")


def test_talent_groups_in_unlock_order(gd):
    groups = talent_groups(gd, 162)
    assert [g["Id"] for g in groups] == [16201, 16202, 16203, 16204, 16205]


def test_talent_nodes_t1(gd):
    effects, keys = talent_nodes(gd, 162, 1)
    assert len(effects) == 10 and keys == [1620116]   # 10 stat nodes + Buried Past
    assert talent_nodes(gd, 162, 0) == ([], [])


def test_t1_starender_from_first_hit(gd, shia_team):
    t1 = simulate(gd, shia_team, Build())
    m0 = replace(shia_team.members[0], talents=0)
    t0 = simulate(gd, replace(shia_team, members=[m0] + shia_team.members[1:]), Build())
    # T0: Starender only from 3 ults x 30 s; T1: from the first hit as well (once per fight)
    assert t0.status_time["starender"] == pytest.approx(90, abs=1.5)
    assert t1.status_time["starender"] > 110
    assert t1.total > t0.total
    assert not any("key talent" in u for u in t1.unknown_modifiers)


def test_once_event_fires_once(gd, shia_team):
    # without ults, a T1 Noya gets exactly one 30 s Starender (from her first hit)
    m0 = shia_team.members[0]
    kit = replace(m0.kit, actions={k: v for k, v in m0.kit.actions.items() if k != "ult"})
    team = replace(shia_team, members=[replace(m0, kit=kit)] + shia_team.members[1:])
    r = simulate(gd, team, Build())
    assert r.status_time["starender"] == pytest.approx(30, abs=0.2)


def test_support_triggers_marks(gd, shia_team):
    r = simulate(gd, shia_team, Build())
    assert r.by_slot.get((1, "mark"), 0) > 0      # Shia's Thunderbolt
    assert r.by_slot.get((0, "mark"), 0) > 0      # Noya still gets some Marks
