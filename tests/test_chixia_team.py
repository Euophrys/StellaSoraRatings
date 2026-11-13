"""Amber + Flora + Chixia: Chixia's summons and the engine features they need
(marker hits, pure statuses, status sums and thresholds)."""
import math

import pytest
from ssr.builds import with_pinks
from ssr.effects import Modifier, Trigger
from ssr.kit import resolve_potential
from ssr.sim import simulate
from ssr.stats import ATK
from ssr.team import Build, load_team

from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it


CHIXIA = 2
CONVERGENCE, CHANT, TIGER, SCALES, HORN_CALL, TRAIL_SEEKER = 514121, 514122, 514123, 514124, 514125, 514126


@pytest.fixture(scope="module")
def team(gd):
    return load_team(gd, TEAMS / "amber_flora_chixia.yaml")


def test_minion_statuses_track_summons(gd, team):
    r = simulate(gd, team, Build())
    casts = r.casts[(CHIXIA, "skill")]
    # Tiger + 3 Dragons per skill cast; the fight may cut the last cast short
    assert 13.767 * (casts - 1) < r.status_time["tiger"] <= 13.767 * casts + 0.1
    assert 0 < r.status_time["dragon"] <= 7.067 * 3 * casts + 0.1


def test_markers_deal_no_damage(gd, team):
    r = simulate(gd, team, Build())
    assert all(v >= 0 for v in r.by_slot.values())
    assert (CHIXIA, "marker") not in r.by_slot


def test_without_tiger_slot_0_is_a_dragon(gd, team):
    r = simulate(gd, with_pinks(team, CHIXIA, [CONVERGENCE, SCALES]), Build())
    assert r.status_time.get("tiger", 0) == 0
    tiger = simulate(gd, team, Build())
    assert r.status_time["dragon"] > tiger.status_time["dragon"]


def test_tiger_stacks_from_markers(gd, team):
    rp = resolve_potential(gd, team.members[CHIXIA].kit, TIGER, 1)
    (m,) = rp.modifiers
    assert m.trigger.event == "marker:self:tiger_tick" and m.trigger.max_stacks == 3 and m.hit_tags == ("tiger",)


def test_status_sum_per_stack(gd, team):  # Horn Call: ATK per minion out (Tiger + Dragons)
    rp = resolve_potential(gd, team.members[CHIXIA].kit, HORN_CALL, 6)
    (m,) = rp.modifiers
    assert m.trigger.event == "while:status:dragon+tiger" and m.trigger.per_stack and m.target == "team"


def _atk(event, per_stack=False):
    return Modifier(stat=ATK, value=1.0, is_pct=True, target="main", source="t",
                    trigger=Trigger(event=event, duration=math.inf, max_stacks=1, per_stack=per_stack))


def test_status_threshold(gd, team):
    base = simulate(gd, team, Build()).total
    one = simulate(gd, team, Build(), extra=[(CHIXIA, _atk("while:status:dragon>=1"))]).total
    three = simulate(gd, team, Build(), extra=[(CHIXIA, _atk("while:status:dragon>=3"))]).total
    never = simulate(gd, team, Build(), extra=[(CHIXIA, _atk("while:status:dragon>=5"))]).total
    assert never == pytest.approx(base)
    assert base < three < one


def test_trail_seeker_procs_per_main_skill(gd, team):
    base = simulate(gd, team, Build())
    ts = simulate(gd, team, Build().with_potential(141, TRAIL_SEEKER, 1))
    assert ts.by_slot[(CHIXIA, "minion")] > base.by_slot[(CHIXIA, "minion")]


def test_recent_condition_needs_same_member(gd, team):  # Snowy Night Surprise: Ode -> Hymn on the summoner's own minions
    def mod(event):
        return Modifier(stat=ATK, value=1.0, is_pct=True, target="main", source="t",
                        trigger=Trigger(event=event, duration=math.inf, max_stacks=1))
    base = simulate(gd, team, Build()).total
    any_minion = simulate(gd, team, Build(), extra=[(CHIXIA, mod("hit:any:minion"))]).total
    gated = simulate(gd, team, Build(), extra=[(CHIXIA, mod("hit:any:minion&recent:skill_dmg:12.25"))]).total
    ult_gated = simulate(gd, team, Build(), extra=[(CHIXIA, mod("hit:any:minion&recent:ult_dmg:60"))]).total
    assert any_minion > base
    assert gated == pytest.approx(base)          # support Chixia never deals Skill DMG
    assert ult_gated > base                       # but she does deal Ult DMG


def test_minion_scope_from_text():
    from ssr.effects import text_reaches_minions
    assert text_reaches_minions("increases the ATK of Ignis Trekkers in the squad and their Minions by {2}.", ATK)
    assert text_reaches_minions("Each of Chixia's minions increases all friendly units' ATK by 27%.", ATK)
    assert not text_reaches_minions("Increases all Ignis Trekkers' ATK by 20%.", ATK)
    # a condition naming minions doesn't scope the buff; "Minion DMG" (a damage type) isn't a scope either
    assert not text_reaches_minions("When at least two Ignis Trekker's minions are present, increases the ATK of Ignis Trekkers.", ATK)
    assert not text_reaches_minions("Walnut deals 50% of ATK as Ignis Minion DMG. Increases Laru's ATK by 10%.", ATK)


def test_trekker_buffs_skip_minions(gd, team):  # user: triggered buffs scoped to "Trekkers" don't reach minions
    import dataclasses
    on_skill = Trigger(event="cast:self:skill", duration=math.inf)
    def atk(minions):
        return Modifier(stat=ATK, value=1.0, is_pct=True, target="self", source="t", minions=minions, trigger=on_skill)
    base = simulate(gd, team, Build())
    trekker = simulate(gd, team, Build(), extra=[(CHIXIA, atk(False))])
    units = simulate(gd, team, Build(), extra=[(CHIXIA, atk(True))])
    assert trekker.by_slot[(CHIXIA, "minion")] == pytest.approx(base.by_slot[(CHIXIA, "minion")])
    assert trekker.by_slot[(CHIXIA, "ult")] > base.by_slot[(CHIXIA, "ult")]
    assert units.by_slot[(CHIXIA, "minion")] > base.by_slot[(CHIXIA, "minion")]
    everything = dataclasses.replace(team, assumptions={**team.assumptions, "minion_buffs": "all"})
    assert simulate(gd, everything, Build(), extra=[(CHIXIA, atk(False))]).by_slot[(CHIXIA, "minion")] > base.by_slot[(CHIXIA, "minion")]


def test_always_on_buffs_snapshot_into_minions(gd, team):  # user: minions use the battle-start stat sheet
    base = simulate(gd, team, Build())
    always = Modifier(stat=ATK, value=1.0, is_pct=True, target="self", source="t", minions=False)
    r = simulate(gd, team, Build(), extra=[(CHIXIA, always)])
    assert r.by_slot[(CHIXIA, "minion")] > base.by_slot[(CHIXIA, "minion")]


def test_uptime_buffs_skip_minions(gd, team):  # averaged come-and-go buffs aren't in the battle-start snapshot
    base = simulate(gd, team, Build())
    part_time = Modifier(stat=ATK, value=1.0, is_pct=True, target="self", source="t", minions=False,
                         trigger=Trigger(event="unknown", duration=math.inf, uptime=0.5))
    r = simulate(gd, team, Build(), extra=[(CHIXIA, part_time)])
    assert r.by_slot[(CHIXIA, "minion")] == pytest.approx(base.by_slot[(CHIXIA, "minion")])
    assert r.by_slot[(CHIXIA, "ult")] > base.by_slot[(CHIXIA, "ult")]
