"""Chitose + Freesia + Teresa: stored skill uses, hit multipliers, cooldown scaling, `&while:` events."""
import math
from dataclasses import replace

import pytest
from ssr.builds import with_pinks
from ssr.effects import Modifier, Trigger
from ssr.kit import HitSpec
from ssr.sim import simulate
from ssr.stats import AUTO_DMG
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

CHITOSE, FREESIA, TERESA = 144, 125, 127
CASCADE, AGAINST_FLOW, SERPENT_GLIDE, MIRROR_BLADE = 514403, 514404, 514401, 514402
FLOWING_CIRCLE = 514410


@pytest.fixture(scope="module")
def cft(gd):
    return load_team(gd, TEAMS / "chitose_freesia_teresa.yaml")


def test_two_stored_uses_at_start(gd, cft):
    # Torrent Flash: SectionAmount 2, UseInterval 0.5 s (data)
    team = with_pinks(cft, 0, [SERPENT_GLIDE, AGAINST_FLOW])
    r = simulate(gd, replace(team, fight_length=3.0), Build())
    assert r.casts[(0, "skill")] == 2


def test_charges_recharge_one_at_a_time(gd, cft):
    # 8 s CD, no CD cut: 1.0, 1.5, then one per 8 s from the first cast: 9, 17, 25, 33 (user: one timer)
    team = with_pinks(cft, 0, [SERPENT_GLIDE, MIRROR_BLADE])
    r = simulate(gd, replace(team, fight_length=40.0), Build())
    assert r.casts[(0, "skill")] == 6


def test_flowing_circle_adds_a_use(gd, cft):
    team = with_pinks(cft, 0, [SERPENT_GLIDE, MIRROR_BLADE])
    short = replace(team, fight_length=2.7)
    assert simulate(gd, short, Build()).casts[(0, "skill")] == 2
    assert simulate(gd, short, Build({(CHITOSE, FLOWING_CIRCLE): 1})).casts[(0, "skill")] == 3


def test_against_the_flow_halves_cd(gd, cft):
    slow = simulate(gd, with_pinks(cft, 0, [CASCADE, SERPENT_GLIDE]), Build())
    fast = simulate(gd, cft, Build())
    assert fast.casts[(0, "skill")] > 1.7 * slow.casts[(0, "skill")]


def _hits(gd, team, build, tag_hit):
    from ssr import sim as S
    seen = []
    orig = S.hit_damage
    S.hit_damage = lambda hd, *a, **k: (seen.append(hd.id) or orig(hd, *a, **k))
    try:
        simulate(gd, team, build)
    finally:
        S.hit_damage = orig
    return seen.count(tag_hit)


def test_scale_replaces_casts(gd, cft):
    # Cascade: every 2nd cast is a Scale (4 hits of 144310301); without it every 3rd (3 hits of 144310002)
    short = replace(cft, fight_length=3.5)   # casts at 1.0, 1.5 (2 stored uses)
    assert _hits(gd, short, Build(), 144310301) == 4
    plain = with_pinks(short, 0, [SERPENT_GLIDE, AGAINST_FLOW])
    assert _hits(gd, plain, Build({(CHITOSE, FLOWING_CIRCLE): 1}), 144310002) == 3   # 3rd cast at 2.0


def test_returning_tide_scale_from_second_cast(gd, cft):
    short = with_pinks(replace(cft, fight_length=3.5), 0, [SERPENT_GLIDE, AGAINST_FLOW])
    b = Build({(CHITOSE, 514409): 1, (CHITOSE, FLOWING_CIRCLE): 1})
    assert _hits(gd, short, b, 144310002) == 6     # casts 2 and 3
    assert _hits(gd, short, b, 144310001) == 2     # cast 1


def test_hit_mult_scales_damage(gd, cft):
    from ssr.kit import ResolvedPotential
    rp = lambda m: ResolvedPotential(potential_id=-1, level=1, modifiers=[], notes=[], add_hits={},
                                     replace_hits={}, add_actions={}, mark_tags=(), extra_casts={}, reset_cd={},
                                     cd_reduce=None, procs=[HitSpec(hit_id=127400001, event="cast:main:ult", mult=m)])
    base = simulate(gd, cft, Build()).total
    full = simulate(gd, cft, Build(), extra=[(2, rp(1.0))]).total - base
    half = simulate(gd, cft, Build(), extra=[(2, rp(0.5))]).total - base
    assert full > 0 and half == pytest.approx(full / 2, rel=0.01)


def test_while_gated_event(gd, cft):
    # A buff that only stacks on Freesia's skill casts made while she is in Berserk
    mk = lambda ev: Modifier(stat=AUTO_DMG, value=1.0, source="t", target="team",
                             trigger=Trigger(event=ev, duration=15.0, max_stacks=1))
    base = simulate(gd, cft, Build()).total
    always = simulate(gd, cft, Build(), extra=[(1, mk("cast:self:skill"))]).total
    gated = simulate(gd, cft, Build(), extra=[(1, mk("cast:self:skill&while:status:berserk"))]).total
    never = simulate(gd, cft, Build(), extra=[(1, mk("cast:self:skill&while:status:nosuch"))]).total
    assert never == pytest.approx(base)
    assert base < gated < always


def test_chill_always_up(gd, cft):
    r = simulate(gd, cft, Build())
    assert r.status_time["chill"] > 110


# ---- disc specs / events added for the Aqua discs

def test_expand_who_tokens():
    from ssr.sim import _expand_who
    classes = [1, 2, 3]
    assert _expand_who("hit:class2:skill_dmg", 3, classes) == "hit:1:skill_dmg"
    assert _expand_who("cast:support:skill|mark:any", 3, classes) == "cast:1:skill|cast:2:skill|mark:any"
    assert _expand_who("mark:support&while:status:x", 3, classes) == "mark:1&while:status:x|mark:2&while:status:x"
    assert _expand_who("hit:class4:any", 3, classes).startswith("never:")
    assert _expand_who("while:status:a>=10", 3, classes) == "while:status:a>=10"


def _disc_status(gd, team, disc_id):
    from ssr.team import FILLER
    return simulate(gd, team, Build(), discs=([(disc_id, 1), (FILLER, 1), (FILLER, 1)], [(FILLER, 1)] * 3))


def test_fleeting_glimmers_tide_weave_from_supports(gd, cft):
    # support skill casts and every 5 s on the field (on_field_5s); Teresa is on the field ~90 s
    r = _disc_status(gd, cft, 214055)
    assert r.status_time["tide_weave"] > 100


def test_soaring_blue_only_from_versatile(gd, cft):
    # Bright Tide comes from Versatile (class 2) Skill DMG: Freesia. Without her it never builds.
    r = _disc_status(gd, cft, 214008)
    assert r.status_time["bright_tide"] > 30
    from ssr.team import load_team
    amber = load_team(gd, TEAMS / "amber_laru_flora.yaml")   # Ignis team: no Versatile Aqua, disc element-locked anyway
    assert "bright_tide" not in _disc_status(gd, amber, 214008).status_time


def test_bedtime_story_reverie_stacks_from_storybook(gd, cft):
    r = _disc_status(gd, cft, 214061)
    assert r.status_time["storybook"] > 100 and r.status_time["reverie"] > 100


def test_mark_applied_event(gd, cft):
    mk = Modifier(stat=AUTO_DMG, value=1.0, source="t", target="team",
                  trigger=Trigger(event="mark_applied:2", duration=1.0, max_stacks=1))
    assert simulate(gd, cft, Build(), extra=[(0, mk)]).total > simulate(gd, cft, Build()).total
