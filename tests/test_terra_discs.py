"""Terra disc specs used by the Gerie / Nazuna / Ridge teams: The Lost Pilgrim, Claw the Claw, The Shining."""
from dataclasses import replace

import pytest

from ssr.effects import Modifier, Trigger, disc_modifiers
from ssr.sim import simulate
from ssr.stats import SKILL_DMG, AUTO_DMG
from ssr.team import FILLER, TEAMS, load_team, team_build

TERRA_DMG, TERRA_TAKEN = 19, 37
PILGRIM, CLAW, SHINING = 214036, 214037, 213020


def _by(mods, stat, part):
    return [m for m in mods if m.stat == stat and part in m.source]


def test_lost_pilgrim_triggers(gd):
    mods, notes = disc_modifiers(gd, PILGRIM, 1)
    assert not notes
    for stat in (SKILL_DMG, AUTO_DMG):
        (m,) = _by(mods, stat, "melody")
        assert m.target == "main" and m.trigger.event == "mark:element3" and m.trigger.duration == 4
        assert m.value == pytest.approx(0.14)
    (cond,) = _by(mods, SKILL_DMG, "harmony1")
    assert cond.trigger.event == "while:on_field:support" and cond.value == pytest.approx(0.05)
    (atk,) = [m for m in mods if "harmony2" in m.source]
    assert atk.trigger.event == "mark:element3" and atk.trigger.max_stacks == 4 and atk.trigger.duration == 5


def test_claw_the_claw_scripted_parts(gd):
    mods, notes = disc_modifiers(gd, CLAW, 1)
    assert not notes   # harmony 1 now has a spec
    (taken,) = _by(mods, TERRA_TAKEN, "melody")   # melody part 2: not in the row's EffectIds
    assert taken.target == "enemy" and taken.trigger.event == "mark:element3"
    assert taken.value == pytest.approx(0.075) and taken.trigger.duration == 4
    (heal,) = _by(mods, TERRA_DMG, "harmony1")
    assert heal.trigger.event == "hit:any:heart|hit:any:wobble" and heal.trigger.duration == 10
    assert heal.value == pytest.approx(0.05)
    (sk,) = _by(mods, SKILL_DMG, "harmony2")
    assert sk.trigger.event == "hit:support:skill_dmg" and sk.trigger.max_stacks == 6


def test_the_shining_triggers(gd):
    mods, notes = disc_modifiers(gd, SHINING, 1)
    assert not notes
    trig = [m for m in _by(mods, SKILL_DMG, "melody") if m.trigger]
    assert trig[0].trigger.event == "cast:any:ult" and trig[0].trigger.duration == 16
    (hit,) = _by(mods, TERRA_DMG, "harmony1")
    assert hit.trigger.event == "hit_taken:main" and not hit.assumed   # when the main is hit (user: ~every 20 s)


def test_no_terra_disc_trigger_left_unknown(gd):
    for d in (PILGRIM, CLAW, SHINING):
        mods, _ = disc_modifiers(gd, d, 1)
        assert not [m for m in mods if m.trigger and m.trigger.event == "unknown" and m.trigger.uptime is None]


@pytest.mark.parametrize("name", ["gerie_nazuna_ridge.yaml", "nazuna_gerie_ridge.yaml"])
def test_heal_events_fire(gd, name):
    """Claw the Claw's harmony 1 keys off heal hits: they must exist in both orders."""
    team = load_team(gd, TEAMS / name)
    team = replace(team, discs_main=[(FILLER, 6)] * 3, enemy=replace(team.enemy, resilience=0))
    base = simulate(gd, team, team_build(team)).total
    probe = Modifier(stat=TERRA_DMG, value=1.0, target="team", source="probe",
                     trigger=Trigger(event="hit:any:heart|hit:any:wobble", duration=10))
    assert simulate(gd, team, team_build(team), extra=[(0, probe)]).total > base * 1.05


def test_terra_discs_add_damage(gd):
    team = load_team(gd, TEAMS / "gerie_nazuna_ridge.yaml")
    team = replace(team, enemy=replace(team.enemy, resilience=0))
    filler = replace(team, discs_main=[(FILLER, 6)] * 3)
    real = replace(team, discs_main=[(PILGRIM, 1), (CLAW, 1), (SHINING, 1)])
    b = team_build(team)
    assert simulate(gd, real, b).total > simulate(gd, filler, b).total
