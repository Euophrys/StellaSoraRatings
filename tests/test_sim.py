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


def test_followup_every_17_glows(gd, team):  # Dawnflare: flurry per 17 Glows; ~every 2 skills with Lucent Blitz
    r = simulate(gd, team, Build())
    # sprint-attack Glows (3 per auto string, Dawnflare) make it more often than every 2 skills
    assert r.casts[(0, "skill")] // 2 <= r.casts[(0, "flurry")] <= r.casts[(0, "skill")]


def test_dawnflare_without_blitz_has_fewer_flurries(gd, team):  # Glows only from auto strings
    from ssr.builds import with_pinks
    r = simulate(gd, with_pinks(team, 0, [516202, 516203]), Build())
    assert r.casts[(0, "flurry")] < simulate(gd, team, Build()).casts[(0, "flurry")] // 2


def test_proc_every_nth_event(gd, team):  # Sinbreaker: Judgment Starfall per 11 Starfalls
    from ssr.builds import with_pinks
    from ssr.kit import HitSpec
    t = with_pinks(team, 0, [516203, 516204])
    base = simulate(gd, t, Build())
    every = simulate(gd, t, Build(), extra=[(0, _rp(procs=[HitSpec(162100007, event="hit:0:starfall", every=1000)]))])
    always = simulate(gd, t, Build(), extra=[(0, _rp(procs=[HitSpec(162100007, event="hit:0:starfall", every=1)]))])
    assert every.total == pytest.approx(base.total)
    assert always.total > base.total


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
    for i in range(3):   # no passive energy (user-tested): Firefly gets 1 ult, Noya and Tilia 2
        assert r.casts[(i, "ult")] >= 1
    assert r.casts[(0, "ult")] >= 2


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


def test_while_support_on_field(gd, team):
    from ssr.effects import Trigger
    base = simulate(gd, team, Build(), discs=FILLERS)
    on = simulate(gd, team, Build(), discs=FILLERS, extra=[(0, Modifier(
        stat=SKILL_DMG, value=0.5, trigger=Trigger("while:on_field:support", 0.0), source="t"))])
    always = simulate(gd, team, Build(), discs=FILLERS, extra=[(0, Modifier(stat=SKILL_DMG, value=0.5, source="t"))])
    assert base.total < on.total < always.total
    assert on.on_field_time[1] > 0 and on.on_field_time[0] == 0


def test_on_field_time_from_kit(gd, team):
    k = team.members[2].kit
    assert k.on_field == {"skill": 2.93, "ult": 4.1}   # user-timed


def test_norm_event_resolves_self_anywhere():
    from ssr.sim import _norm_event
    assert _norm_event("while:on_field:self", 2) == "while:on_field:2"
    assert _norm_event("cast:self:skill", 1) == "cast:1:skill"
    assert _norm_event("hit:main:skill_dmg", 1) == "hit:0:skill_dmg"


def test_glimmer_status_tracked(gd, team):
    r = simulate(gd, team, Build())
    assert r.status_time.get("glimmer", 0) > 10


def test_stacks_from_status(gd, team):
    from ssr.effects import Trigger
    from ssr.stats import elem_stat, ELEM_TAKEN_BASE
    base = simulate(gd, team, Build())
    one = simulate(gd, team, Build(), extra=[(0, Modifier(stat=elem_stat(ELEM_TAKEN_BASE, 5), value=0.02, target="enemy",
                                                          trigger=Trigger("mark:0", 10.0, max_stacks=20), source="t"))])
    per = simulate(gd, team, Build(), extra=[(0, Modifier(stat=elem_stat(ELEM_TAKEN_BASE, 5), value=0.02, target="enemy",
                                                          trigger=Trigger("mark:0", 10.0, max_stacks=20, stacks_from="glimmer"), source="t"))])
    assert base.total < one.total < per.total


def test_target_intersection():
    from ssr.sim import _targets
    # classes / elements of a squad: Lux Versatile, Ignis Versatile, Lux Support
    assert _targets("class:2/element:5", 0, 3, [2, 2, 3], [5, 1, 5]) == [0]
    assert _targets("class:3/element:1", 0, 3, [2, 2, 3], [5, 1, 5]) == []


def _fl_noya_squad(gd, *supports):
    from ssr.team import team_from_doc
    members = [{"trekker": "Firstlight Noya", "role": "main"}] + [{"trekker": n, "role": "support"} for n in supports]
    return team_from_doc(gd, {"members": members, "discs": {"main": ["filler"] * 3, "support": ["filler"] * 3},
                              "enemy": {"res": 250, "defense": 500}})


def _gain(gd, team, build, who):
    base = simulate(gd, team, Build(), discs=FILLERS)
    return simulate(gd, team, build, discs=FILLERS).by_member[who] / base.by_member[who] - 1


def test_astral_brilliance_counts_lux_trekkers_in_the_squad(gd):
    astral = Build({(162, 516212): 6})
    all_lux = _gain(gd, _fl_noya_squad(gd, "Firefly", "Tilia"), astral, 0)
    alone = _gain(gd, _fl_noya_squad(gd, "Kasimira", "Iris"), astral, 0)   # Ignis and Aqua: only Noya is Lux
    assert alone > 0 and all_lux > 2 * alone


def test_lucent_tide_buffs_lux_versatile_only(gd):
    tide = Build({(162, 516207): 6})
    assert _gain(gd, _fl_noya_squad(gd, "Firefly", "Tilia"), tide, 1) > 0        # Lux Versatile
    assert _gain(gd, _fl_noya_squad(gd, "Kasimira", "Tilia"), tide, 1) == pytest.approx(0)   # Ignis Versatile
