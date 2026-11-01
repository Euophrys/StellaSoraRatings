"""Amber + Snowish Laru + Flora: kit behaviour and the engine features it needs."""
import math

import pytest
from ssr.builds import with_pinks
from ssr.effects import Modifier, Trigger, disc_modifiers
from ssr.kit import HitSpec, ResolvedPotential
from ssr.sim import simulate, _event_matches, _norm_event
from ssr.stats import AUTO_DMG
from ssr.team import Build, load_team, TEAMS

AMBER, LARU, FLORA = 103, 158, 126
PTC, ECHO, DF, BS = 510303, 510304, 510301, 510302


@pytest.fixture(scope="module")
def amber(gd):
    return load_team(gd, TEAMS / "amber_laru_flora.yaml")


def _rp(**kw):
    base = dict(potential_id=-1, level=1, modifiers=[], notes=[], add_hits={}, replace_hits={}, add_actions={},
                mark_tags=(), extra_casts={}, reset_cd={}, cd_reduce=None, procs=[])
    base.update(kw)
    return ResolvedPotential(**base)


def test_event_alternatives():
    assert _event_matches(_norm_event("cast:self:skill|cast:self:recast", 0), "cast:0:recast")
    assert not _event_matches(_norm_event("cast:self:skill|cast:self:recast", 0), "cast:0:ult")


def test_laru_never_ults_and_stays_15s(gd, amber):
    r = simulate(gd, amber, Build())
    assert (1, "ult") not in r.casts
    # 18 s CD, 15.3 s on field per cast (user, video): on field ~15.3/18 of the fight
    assert 0.78 < r.on_field_time[1] / 120 < 0.9


def test_recast_follows_every_skill(gd, amber):  # Precise Temperature Control
    r = simulate(gd, amber, Build())
    assert r.casts[(0, "recast")] == r.casts[(0, "skill")]


def test_dominant_firepower_36_round_magazine(gd, amber):
    base = simulate(gd, with_pinks(amber, 0, [ECHO, BS]), Build())
    df = simulate(gd, with_pinks(amber, 0, [DF, BS]), Build())
    assert df.by_slot[(0, "auto")] > base.by_slot[(0, "auto")]


def test_reset_on_clears_stacks(gd, amber):  # Ardent-Trigger-style stacks reset on every reload
    stack = lambda reset: Modifier(stat=AUTO_DMG, value=0.05, hit_tags=("auto",), source="t",
                                   trigger=Trigger(event="hit:self:auto", duration=math.inf, max_stacks=36, reset_on=reset))
    keep = simulate(gd, amber, Build(), extra=[(0, stack(()))])
    reset = simulate(gd, amber, Build(), extra=[(0, stack(("hit:self:mag_end",)))])
    base = simulate(gd, amber, Build())
    assert base.total < reset.total < keep.total


def test_proc_when_gated_on_status(gd, amber):
    proc = lambda when: _rp(procs=[HitSpec(126522001, event="hit:0:any", icd=1.0, when=when)])
    never = simulate(gd, amber, Build(), extra=[(2, proc("while:status:nonexistent"))])
    gated = simulate(gd, amber, Build(), extra=[(2, proc("while:status:mindflare"))])
    always = simulate(gd, amber, Build(), extra=[(2, proc(""))])
    assert never.total == pytest.approx(simulate(gd, amber, Build()).total)
    assert never.total < gated.total < always.total


def test_flora_mindflare_count_follows_ashes(gd, amber):  # buff `add` + `requires`/`excludes`
    base = simulate(gd, amber, Build())
    ashes = simulate(gd, with_pinks(amber, 2, [512623, 512624]), Build())
    assert base.status_time["mindflare"] > 0 and ashes.status_time["mindflare"] > 0
    assert ashes.by_slot[(2, "skill")] != base.by_slot[(2, "skill")]


def test_minion_hits_use_minion_slot(gd, amber):
    r = simulate(gd, amber, Build())
    assert r.by_slot[(1, "minion")] > 0


def test_negative_dmg_taken_is_not_an_enemy_debuff(gd):
    mods, _ = disc_modifiers(gd, 214030, 1)   # A Moment in the Afternoon: "reduces DMG taken by 10%"
    assert not [m for m in mods if m.target == "enemy" and m.value < 0]


def test_skill_cd_starts_after_recast(gd, amber):  # 2.233 s cast + 2.233 s recast, then the 8 s CD
    r = simulate(gd, amber, Build())
    period = 2 * 2.233 + 8.0
    assert r.casts[(0, "skill")] == pytest.approx(120 / period, abs=1.5)


def test_disc_icd_and_always(gd):  # Voyage Blueprint: Ignis DMG 12 s, once per 20 s; Skill DMG always on
    mods, _ = disc_modifiers(gd, 214013, 1)
    ignis = [m for m in mods if m.stat == 18][0]
    assert ignis.trigger.icd == 20 and ignis.trigger.duration == 12
    assert [m for m in mods if m.stat == 57][0].trigger is None
