import pytest
from ssr.sim import simulate
from ssr.team import Build, FILLER
from ssr.effects import Modifier
from ssr.kit import ResolvedPotential
from ssr.stats import SKILL_DMG


def _rp(**kw):
    base = dict(potential_id=-1, level=1, modifiers=[], notes=[], add_hits={}, replace_hits={}, add_actions={},
                mark_tags=(), extra_casts={}, reset_cd={}, cd_reduce=None, procs=[])
    base.update(kw)
    return ResolvedPotential(**base)


def test_cast_counts_cooldown_bound(gd, team):  # Noya skill CD 10 s, 120 s fight, first cast at 1.0 s
    r = simulate(gd, team, Build())
    assert 11 <= r.casts[(0, "skill")] <= 12


def test_followup_every_second_skill(gd, team):  # Dawnflare pink: flurry after every 2nd skill cast
    r = simulate(gd, team, Build())
    assert r.casts[(0, "flurry")] == r.casts[(0, "skill")] // 2


def test_opening_order(gd, team):
    r = simulate(gd, team, Build())
    assert r.first_cast[(1, "skill")] == 0.0 and r.first_cast[(2, "skill")] == 0.0
    assert r.first_cast[(0, "skill")] == pytest.approx(1.0)


FILLERS = ([(FILLER, 6)] * 3, [(FILLER, 6)] * 3)


def test_skill_dmg_modifier_only_moves_skill_hits(gd, team):  # empty Skill DMG bucket: all-filler discs
    base = simulate(gd, team, Build(), discs=FILLERS)
    buffed = simulate(gd, team, Build(), discs=FILLERS, extra=[(0, Modifier(stat=SKILL_DMG, value=0.2, source="test"))])
    assert buffed.by_slot[(0, "auto")] == pytest.approx(base.by_slot[(0, "auto")])
    assert buffed.by_slot[(0, "skill")] == pytest.approx(base.by_slot[(0, "skill")] * 1.2)


def test_extra_cast_increases_skill_casts(gd, team):
    base = simulate(gd, team, Build())
    more = simulate(gd, team, Build(), extra=[(0, _rp(extra_casts={"skill": 1}))])
    assert more.casts[(0, "skill")] == 2 * base.casts[(0, "skill")]


def test_ults_cast(gd, team):
    r = simulate(gd, team, Build())
    for i in range(3):
        assert r.casts[(i, "ult")] >= 2


def test_marks_trigger(gd, team):
    r = simulate(gd, team, Build())
    assert r.by_slot.get((0, "mark"), 0) > 0


def test_deterministic(gd, team):
    assert simulate(gd, team, Build()).total == simulate(gd, team, Build()).total


def test_every_n_events_trigger(gd, team):
    from ssr.effects import Trigger
    base = simulate(gd, team, Build(), discs=FILLERS)
    never = simulate(gd, team, Build(), discs=FILLERS, extra=[(0, Modifier(
        stat=SKILL_DMG, value=0.5, trigger=Trigger("hit:0:skill_dmg", 5.0, every=10**6), source="t"))])
    often = simulate(gd, team, Build(), discs=FILLERS, extra=[(0, Modifier(
        stat=SKILL_DMG, value=0.5, trigger=Trigger("hit:0:skill_dmg", 5.0, every=3), source="t"))])
    assert never.total == pytest.approx(base.total) and often.total > base.total


def test_class_target_reaches_versatile_only(gd, team):  # Firefly is class 2 (Versatile)
    from ssr.stats import ATK
    base = simulate(gd, team, Build(), discs=FILLERS)
    r = simulate(gd, team, Build(), discs=FILLERS, extra=[(0, Modifier(stat=ATK, value=0.5, is_pct=True, target="class:2", source="t"))])
    assert r.by_member[1] > base.by_member[1] and r.by_member[2] == pytest.approx(base.by_member[2])
