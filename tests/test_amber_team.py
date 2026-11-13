"""Amber + Snowish Laru + Flora: kit behaviour and the engine features it needs."""
import math
from dataclasses import replace

import pytest
from ssr.builds import with_pinks
from ssr.effects import Modifier, Trigger, disc_modifiers
from ssr.kit import ActionSpec, Followup, HitSpec, ResolvedPotential, SPECS, load_kit, resolve_potential
from ssr.sim import simulate, _event_matches, _norm_event
from ssr.stats import AUTO_DMG
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

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


def test_skill_cd_starts_after_recast(gd, amber):  # 2.333 s cast + 1.833 s recast, then the 8 s CD
    r = simulate(gd, _no_cancel(amber), Build())
    period = 2.333 + 1.833 + 8.0
    assert r.casts[(0, "skill")] == pytest.approx(120 / period, abs=1.5)


def test_disc_icd_and_always(gd):  # Voyage Blueprint: Ignis DMG 12 s, once per 20 s; Skill DMG always on
    mods, _ = disc_modifiers(gd, 214013, 1)
    ignis = [m for m in mods if m.stat == 18][0]
    assert ignis.trigger.icd == 20 and ignis.trigger.duration == 12
    assert [m for m in mods if m.stat == 57][0].trigger is None


def _no_cancel(team):
    return replace(team, assumptions={**team.assumptions, "dodge_cancel": False})


def _dodges(gd, team):
    """Number of main dodges: a 0.05 s status (one tick), so its time counts them."""
    st = Modifier(stat=0, value=0, target="main", name="dodged", source="test",
                  trigger=Trigger(event="dodge:main", duration=0.05))
    r = simulate(gd, team, Build(), extra=[(0, st)])
    return round(r.status_time.get("dodged", 0.0) / 0.05), r


def test_recast_gap_with_and_without_dodge_cancel(gd, amber):
    # User, frame-timed (30 fps): recast ready 2,10 after the skill; or dodge at 1,24 (keeps every hit) and recast 0,10 later.
    gap = lambda r: r.first_cast[(0, "recast")] - r.first_cast[(0, "skill")]
    assert gap(simulate(gd, _no_cancel(amber), Build())) == pytest.approx(2 + 10 / 30, abs=0.05)
    assert gap(simulate(gd, amber, Build())) == pytest.approx(1.8 + 10 / 30, abs=0.05)


def test_dodge_cancel_dodges_on_both_casts(gd, amber):
    rare = replace(amber, assumptions={**amber.assumptions, "dodge_interval": 1000})
    dodges, r = _dodges(gd, rare)
    assert dodges == pytest.approx(r.casts[(0, "skill")] + r.casts[(0, "recast")], abs=3)
    assert _dodges(gd, _no_cancel(rare))[0] == 0


def test_cancel_dodges_replace_periodic_ones(gd, amber):  # one every ~6 s: the 10 s schedule never comes due
    rare = replace(amber, assumptions={**amber.assumptions, "dodge_interval": 1000})
    assert _dodges(gd, amber)[0] == pytest.approx(_dodges(gd, rare)[0], abs=2)


def test_skill_cd_starts_at_the_recasts_dodge(gd, amber):
    # User: the CD starts at the dodge. Cycle with dodges: 2.133 s + the dodge at +1.433 s + 8 s CD; without: 2.333 + 1.833 + 8.
    long = replace(amber, fight_length=600.0)
    assert simulate(gd, long, Build()).casts[(0, "skill")] == pytest.approx(600 / (8 + 2.133 + 1.433), abs=1)
    assert simulate(gd, _no_cancel(long), Build()).casts[(0, "skill")] == pytest.approx(600 / (8 + 2.333 + 1.833), abs=1)


@pytest.mark.parametrize("build", [Build(), Build().with_potential(AMBER, 510309, 6)], ids=["base", "grand_finale"])
def test_default_dodges_keep_every_hit(gd, amber, build):
    t = replace(with_pinks(amber, 0, [PTC, BS]), fight_length=600.0)   # no Echo: its procs depend on timing
    per_cast = lambda r: r.by_slot[(0, "skill")] / r.casts[(0, "skill")]
    assert per_cast(simulate(gd, t, build)) == pytest.approx(per_cast(simulate(gd, _no_cancel(t), build)), rel=0.03)


def test_dodge_cancel_cuts_later_hits(gd, amber):
    t = with_pinks(amber, 0, [BS, ECHO])
    def recast(**kw):
        hits = [HitSpec(103310002, offset=0.2, tags=("fj",)), HitSpec(103310002, offset=1.0, tags=("fj",))]
        return _rp(add_actions={"recast": ActionSpec(name="recast", hits=hits, lock=2.0, followup=Followup(after="skill"), **kw)})
    skill = lambda **kw: simulate(gd, t, Build(), extra=[(0, recast(**kw))]).by_slot[(0, "skill")]
    assert skill(dodge_at=0.5, dodge_duration=0.9) < skill()


def test_recast_after_a_marked_cast_uses_its_own_hit_rows(gd):
    # User's clips with a Mark: both big hits are the same (10109 and 10109, 12801 and 12801), about 1.3x a volley hit (7454, 10408): 22.7% / 17%.
    recast = load_kit(gd, SPECS / "103.yaml", "main").potentials[PTC].add_actions["recast"]
    assert [h.hit_id for h in recast.hits if h.count == 1] == [103303001, 103303001]
    assert sum(h.count for h in recast.hits if h.hit_id == 103303003) == 8
    assert sum(h.count for h in recast.hits) == 10


def test_ptc_bonus_is_a_separate_multiplier(gd):
    # EAT 85 "DMG Multiplier": about 2x from the first cast to the recast, which +65% in the DMG bucket can't reach (user's clips).
    kit = load_kit(gd, SPECS / "103.yaml", "main")
    assert all(h.mult == pytest.approx(1.65) for h in kit.potentials[PTC].add_actions["recast"].hits)
    assert resolve_potential(gd, kit, PTC, 1).modifiers == []


def test_recast_can_trigger_marks(gd):  # user: Incineration on its shots 1 and 3 when a Mark is up
    recast = load_kit(gd, SPECS / "103.yaml", "main").potentials[PTC].add_actions["recast"]
    assert all(h.triggers_mark for h in recast.hits)


def test_grand_finale_adds_big_rounds_to_the_first_cast_only(gd):
    # User, frame by frame: first cast 2 + 2 big + 8 small, recast 1 + 1 big + 8 small.
    add = load_kit(gd, SPECS / "103.yaml", "main").potentials[510309].add_hits
    assert set(add) == {"skill"}
    assert [(h.hit_id, h.count) for h in add["skill"]] == [(103310002, 1), (103310002, 1)]


def test_dodge_cancel_needs_the_recast(gd, amber):  # nothing to cancel into without Precise Temperature Control
    t = with_pinks(amber, 0, [ECHO, BS])
    assert simulate(gd, t, Build()).total == pytest.approx(simulate(gd, _no_cancel(t), Build()).total)
