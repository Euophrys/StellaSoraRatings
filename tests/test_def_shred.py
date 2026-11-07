"""Enemy DEF reductions: flat DEF on the enemy lowers its DEF before defAmend (docs/reference/damage-formula/2.def.c)."""
import pytest
from dataclasses import replace
from ssr.effects import Modifier
from ssr.formula import def_amend
from ssr.sim import simulate
from ssr.stats import DEF
from ssr.team import Build, load_team, TEAMS


def _bar_off(team):
    return replace(team, enemy=replace(team.enemy, resilience=0))


def test_flat_def_shred_scales_by_def_amend(gd, team):
    team = _bar_off(team)
    base = simulate(gd, team, Build()).total
    shred = Modifier(stat=DEF, value=-150, target="enemy", source="test")
    r = simulate(gd, team, Build(), extra=[(0, shred)]).total
    assert r / base == pytest.approx(def_amend(350) / def_amend(500), rel=1e-9)   # +20.45% (reference)


def test_def_cannot_go_below_zero(gd, team):
    team = _bar_off(team)
    big = simulate(gd, team, Build(), extra=[(0, Modifier(stat=DEF, value=-5000, target="enemy", source="t"))]).total
    zero = simulate(gd, team, Build(), extra=[(0, Modifier(stat=DEF, value=-500, target="enemy", source="t"))]).total
    assert big == pytest.approx(zero, rel=1e-12)


def test_ridge_root_grasp_and_corrosive_vines(gd):
    """Ridge Lv6: Corrosive Vines 5 x -30 while seeds land, Root Grasp -151 on Seed Orb targets: both raise damage."""
    t = _bar_off(load_team(gd, TEAMS / "gerie_nazuna_ridge.yaml"))
    base = simulate(gd, t, Build()).total
    vines = simulate(gd, t, Build().with_potential(116, 511626, 6)).total
    grasp = simulate(gd, t, Build().with_potential(116, 511629, 6)).total
    assert vines > base * 1.02 and grasp > base * 1.05
