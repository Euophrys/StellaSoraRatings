"""Nanoha / Ann / Canace: clone pool (ult), additive minion rules, pct overrides, `&recent` on two-part events."""
import pytest
from ssr.kit import resolve_potential
from ssr.sim import _norm_event, simulate
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

NANOHA = 119


def _team(gd):
    return load_team(gd, TEAMS / "nanoha_ann_canace.yaml")


def test_norm_event_replaces_self_before_suffix():
    assert _norm_event("mark:self&recent:shuriken:0.05", 2) == "mark:2&recent:shuriken:0.05"
    assert _norm_event("hit:self:mark&recent:ult_dmg:0.05", 0) == "hit:0:mark&recent:ult_dmg:0.05"
    assert _norm_event("cast:self:skill|mark:main", 1) == "cast:1:skill|mark:0"


def test_splendid_vortex_triggers_on_skill_marks(gd):
    t = _team(gd)
    base = simulate(gd, t, Build()).total
    assert simulate(gd, t, Build().with_potential(NANOHA, 511909, 6)).total > base * 1.02


def test_wind_whispers_adds_clone_lifetime(gd):
    """duration_add: Lv3 adds 3 s (data) to each clone pair (the last pair may be cut off by the fight's end)."""
    t = _team(gd)
    base = simulate(gd, t, Build())
    ww = simulate(gd, t, Build().with_potential(NANOHA, 511943, 3))
    n = base.casts[(0, "ult")]
    assert ww.casts[(0, "ult")] == n
    gain = ww.status_time["clone"] - base.status_time["clone"]
    assert 3.0 * (n - 1) - 0.2 <= gain <= 3.0 * n + 0.2


def test_infinite_shade_third_clone(gd):
    t = _team(gd)
    base = simulate(gd, t, Build()).by_slot[(0, "ult")]
    shade = simulate(gd, t, Build().with_potential(NANOHA, 511942, 1))
    assert shade.by_slot[(0, "ult")] > base * 1.5   # 3 clones instead of 2, plus Ult DMG


def test_blossom_rhyme_is_pct_atk_on_clones(gd):
    rp = resolve_potential(gd, _team(gd).members[0].kit, 511941, 6)
    (m,) = rp.modifiers
    assert m.is_pct and m.hit_tags == ("clone",)
