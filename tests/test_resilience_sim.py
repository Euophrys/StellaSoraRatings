import pytest
from dataclasses import replace
from ssr.sim import simulate
from ssr.team import Build, load_team
from ssr.effects import Modifier, Trigger
from ssr.stats import SKILL_DMG
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

PRE_RESILIENCE_TOTAL = 222416708.8703382   # fl_noya_skill, Build(), bar off. Was 223,698,051.888 before Ripples of Nostalgia harmony 1 and Shock (A Moment in the Afternoon) got real triggers (2026-11-04). Was 239,320,242.148 before passive energy was removed (2026-11-03, user: no passive energy)


def _with_enemy(team, **kw):
    return replace(team, enemy=replace(team.enemy, **kw))


def test_bar_off_matches_pre_resilience_totals(gd, team):
    team = replace(team, assumptions={**team.assumptions, "harmony_notes": 0, "dodge_time": 0,
                                      "stack_timers": "independent"})   # total predates notes, dodge costs, refreshing stacks
    r = simulate(gd, _with_enemy(team, resilience=0, res=145.0), Build())   # total predates raw enemy RES (was 250 - 105)
    assert r.total == pytest.approx(PRE_RESILIENCE_TOTAL, rel=1e-12) and r.breaks == []


def test_breaks_raise_damage(gd, team):
    off = simulate(gd, _with_enemy(team, resilience=0), Build())
    on = simulate(gd, team, Build())   # fl_noya_skill now loads as Generic (250M bar)
    assert on.breaks and on.total > off.total
    assert on.broken_time == pytest.approx(10 * len(on.breaks), abs=10)   # last break may be cut by the fight end


def test_break_ratio_scales_window(gd, team):
    small = _with_enemy(team, resilience=1e7)   # many breaks
    a = simulate(gd, replace(small, enemy=replace(small.enemy, break_ratio=1.0)), Build())
    b = simulate(gd, small, Build())
    assert b.total > a.total and a.breaks == b.breaks   # break timing doesn't depend on the ratio


def test_breaking_hit_not_boosted(gd, team):
    # Bar of 1 and a 1000 s break: the first hit breaks it and the enemy stays broken all fight.
    # If the breaking hit were boosted, ratio 2.0 would give exactly 2x the bar-off total.
    t = _with_enemy(team, resilience=1.0, break_time=1000.0, break_ratio=2.0)
    on, off = simulate(gd, t, Build()).total, simulate(gd, _with_enemy(team, resilience=0), Build()).total
    assert 1.9 * off < on < 2 * off - 1.0


def test_minions_feed_bar(gd):
    t = load_team(gd, TEAMS / "amber_laru_flora.yaml")
    r = simulate(gd, t, Build())
    assert r.resilience_by_member[1] > 0   # Snowish Laru: minion damage, x1.5 owner multiplier


def test_resilience_uses_trekker_multiplier(gd, team):
    amber = load_team(gd, TEAMS / "amber_laru_flora.yaml")
    r = simulate(gd, _with_enemy(amber, resilience=0), Build())     # bar off: no break ratio anywhere
    assert r.resilience_by_member[0] == pytest.approx(r.by_member[0])          # Amber x1.0
    n = simulate(gd, _with_enemy(team, resilience=0), Build())
    assert n.resilience_by_member[0] == pytest.approx(1.5 * n.by_member[0])    # Noya x1.5


def test_while_broken_condition(gd, team):
    from test_sim import _rp
    mod = Modifier(stat=SKILL_DMG, value=1.0, target="self", trigger=Trigger(event="while:broken", duration=0))
    off = _with_enemy(team, resilience=0)
    # bar off: falls back to the unknown_trigger_uptime assumption (spec): on at uptime 1.0, off at 0
    assert simulate(gd, off, Build(), extra=[(0, _rp(modifiers=[mod]))]).total > simulate(gd, off, Build()).total
    off0 = replace(off, assumptions={**off.assumptions, "unknown_trigger_uptime": 0.0})
    assert simulate(gd, off0, Build(), extra=[(0, _rp(modifiers=[mod]))]).total == pytest.approx(simulate(gd, off0, Build()).total)
    # bar on: active only while broken, so less than always-on
    on = simulate(gd, team, Build(), extra=[(0, _rp(modifiers=[mod]))]).total
    assert simulate(gd, team, Build()).total < on < simulate(gd, off, Build(), extra=[(0, _rp(modifiers=[mod]))]).total


def test_no_breaks_mode(gd, team):
    from test_sim import _rp
    assert simulate(gd, team, Build()).breaks
    never = replace(team, enemy=replace(team.enemy, breaks=False))
    r = simulate(gd, never, Build())
    assert not r.breaks and r.broken_time == 0.0
    assert r.total == pytest.approx(simulate(gd, _with_enemy(team, resilience=0), Build()).total)
    # unlike the bar-off fallback, a while:broken line is off rather than always on, and while:not:broken stays on
    broken = Modifier(stat=SKILL_DMG, value=1.0, target="self", trigger=Trigger(event="while:broken", duration=0))
    assert simulate(gd, never, Build(), extra=[(0, _rp(modifiers=[broken]))]).total == pytest.approx(r.total)
    unbroken = Modifier(stat=SKILL_DMG, value=1.0, target="self", trigger=Trigger(event="while:not:broken", duration=0))
    assert simulate(gd, never, Build(), extra=[(0, _rp(modifiers=[unbroken]))]).total > r.total


def test_enemy_ability_applies(gd):
    t = load_team(gd, TEAMS / "fl_noya_skill.yaml")
    from ssr.enemies import enemy_from_doc
    lithe = replace(t, enemy=enemy_from_doc(gd, {"preset": "lithe_beauty", "res": t.enemy.res, "resilience": 0}))
    plain = _with_enemy(t, resilience=0)
    assert simulate(gd, lithe, Build()).total > simulate(gd, plain, Build()).total


def test_enemy_hit_tags_by_member_and_bucket(gd):
    """Enemy modifiers with hit_tags by_support / by_main / <bucket>_dmg only reach those hits."""
    from ssr.effects import Modifier
    t = _with_enemy(load_team(gd, TEAMS / "bb_noya_shia_tilia_ingame.yaml"), resilience=0)
    t = replace(t, enemy=replace(t.enemy, ability=()))   # only the test's line
    base = simulate(gd, t, Build())

    def with_ability(tags):
        m = Modifier(stat=53, value=1.0, target="enemy", hit_tags=tags)   # DMG Taken +100% on those hits
        return simulate(gd, replace(t, enemy=replace(t.enemy, ability=(m,))), Build())
    sup = with_ability(("by_support",))
    assert sup.by_member[0] == pytest.approx(base.by_member[0])
    assert sup.by_member[1] == pytest.approx(2 * base.by_member[1]) and sup.by_member[2] == pytest.approx(2 * base.by_member[2])
    main = with_ability(("by_main",))
    assert main.by_member[0] == pytest.approx(2 * base.by_member[0]) and main.by_member[1] == pytest.approx(base.by_member[1])
    skill = with_ability(("skill_dmg",))
    assert base.by_slot[(0, "skill")] > 0 and base.by_slot[(0, "auto")] > 0
    assert skill.by_slot[(0, "skill")] == pytest.approx(2 * base.by_slot[(0, "skill")])
    assert skill.by_slot[(0, "auto")] == pytest.approx(base.by_slot[(0, "auto")])


def test_form_breaker_removes_expected_resilience(gd):
    t = load_team(gd, TEAMS / "mistique_chixia_cosette.yaml")   # Cosette idx 2 with Phantom Mark (13 claws)
    base = simulate(gd, t, Build())
    fb = simulate(gd, t, Build().with_potential(142, 514229, 1))
    casts = fb.casts[(2, "skill")]
    extra = fb.resilience_by_member[2] - base.resilience_by_member[2]
    per_cast = 3.0533 * 0.004 * 250e6
    # the last cast's claws can fall past the fight's end (it does with no passive energy: 10 of 11 casts land)
    assert (casts - 1) * per_cast * 0.98 <= extra <= casts * per_cast * 1.02


def test_chance_proc_damage_is_expected_value(gd, team):
    # bar off: break timing (moved by the proc's own damage) would otherwise swamp the expected-value check
    from test_sim import _rp
    from ssr.kit import HitSpec
    team = _with_enemy(team, resilience=0)
    full = simulate(gd, team, Build(), extra=[(0, _rp(procs=[HitSpec(162100007, event="cast:0:skill")]))]).total
    half = simulate(gd, team, Build(), extra=[(0, _rp(procs=[HitSpec(162100007, event="cast:0:skill", chance=0.5)]))]).total
    base = simulate(gd, team, Build()).total
    assert half - base == pytest.approx((full - base) / 2, rel=0.01)


def test_decisive_strike_second_line_needs_break(gd):
    from ssr.effects import disc_modifiers
    mods = [m for m in disc_modifiers(gd, 214007, 1)[0] if "harmony1" in m.source]
    assert [m.trigger.event for m in mods] == ["hit:main:skill_dmg", "hit:any:any&while:broken"]


def test_chance_with_restart_is_rejected(gd, team):
    # expected-value scaling can't express "a refreshed DoT with a proc chance"; refuse rather than overrate it
    from test_sim import _rp
    from ssr.kit import HitSpec
    p = HitSpec(162100007, event="cast:0:skill", count=40, interval=1.0, restart=True, chance=0.5)
    with pytest.raises(ValueError, match="restart"):
        simulate(gd, team, Build(), extra=[(0, _rp(procs=[p]))])
