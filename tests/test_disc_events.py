"""Engine pieces added for the 2026-11-04 disc pass: clock events (timer, dodge, hit taken), battle-start Energy,
while:vul / while:in_action conditions and tagged Mark hits."""
import math
import pytest
from dataclasses import replace
from ssr.effects import Modifier, Trigger, disc_modifiers
from ssr.sim import simulate
from ssr.stats import SKILL_DMG, START_ENERGY
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it


def _bar_off(team):
    return replace(team, enemy=replace(team.enemy, resilience=0))


def _status(name, event, duration=1.0):
    return Modifier(stat=0, value=0, target="main", name=name, source="test",
                    trigger=Trigger(event=event, duration=duration))


def test_timer_fires_from_battle_start(gd, team):
    team = _bar_off(team)
    r = simulate(gd, team, Build(), extra=[(0, _status("t20", "timer:20"))])
    fires = math.ceil(team.fight_length / 20)   # 0, 20, 40, ... (one at the very end adds nothing)
    assert r.status_time["t20"] == pytest.approx(fires * 1.0, abs=0.2)


def test_dodge_every_interval(gd, team):
    team = _bar_off(team)
    r = simulate(gd, team, Build(), extra=[(0, _status("dodged", "dodge:main"))])
    assert r.status_time["dodged"] == pytest.approx((math.ceil(team.fight_length / 10) - 1) * 1.0, abs=0.2)   # 10, 20, ...
    team5 = replace(team, assumptions={**team.assumptions, "dodge_interval": 5})
    r5 = simulate(gd, team5, Build(), extra=[(0, _status("dodged", "dodge:main"))])
    assert r5.status_time["dodged"] > 1.8 * r.status_time["dodged"]


def test_no_hits_taken_while_broken(gd, team):
    off = simulate(gd, _bar_off(team), Build(), extra=[(0, _status("hit", "hit_taken:main"))])
    many = replace(team, enemy=replace(team.enemy, resilience=1e7))   # breaks often
    on = simulate(gd, many, Build(), extra=[(0, _status("hit", "hit_taken:main"))])
    assert on.breaks and on.status_time["hit"] < off.status_time["hit"]


def test_battle_start_energy_brings_the_first_ult_forward(gd, team):
    team = _bar_off(team)
    base = simulate(gd, team, Build())
    boost = simulate(gd, team, Build(), extra=[(0, Modifier(stat=START_ENERGY, value=100, target="self", source="t"))])
    assert boost.first_cast[(0, "ult")] < base.first_cast[(0, "ult")]


def test_miraculous_anthem_reads_its_energy(gd):
    mods, notes = disc_modifiers(gd, 213021, 1)
    assert [m.value for m in mods if m.stat == START_ENERGY] == [15]
    assert not any("EffectType 34" in n for n in notes)


def test_while_vul_needs_that_elements_taken_debuff(gd, team):
    team = _bar_off(team)   # FL Noya's discs put Lux DMG Taken on the enemy; nothing applies Aqua DMG Taken
    base = simulate(gd, team, Build()).total
    lux = Modifier(stat=SKILL_DMG, value=0.5, target="main", source="t", trigger=Trigger(event="while:vul:5", duration=0))
    aqua = replace(lux, trigger=Trigger(event="while:vul:1", duration=0))
    assert simulate(gd, team, Build(), extra=[(0, lux)]).total > base
    assert simulate(gd, team, Build(), extra=[(0, aqua)]).total == pytest.approx(base, rel=1e-12)


def test_while_in_action_covers_the_ult(gd, team):
    team = _bar_off(team)
    base = simulate(gd, team, Build()).total
    m = Modifier(stat=3, value=0.5, is_pct=True, target="main", source="t",   # HP%: FL Noya scales with Max HP
                 trigger=Trigger(event="while:in_action:0:ult", duration=0))
    never = replace(m, trigger=Trigger(event="while:in_action:0:nothing", duration=0))
    assert simulate(gd, team, Build(), extra=[(0, m)]).total > base
    assert simulate(gd, team, Build(), extra=[(0, never)]).total == pytest.approx(base, rel=1e-12)


def test_mark_hit_tags(gd):
    t = _bar_off(load_team(gd, TEAMS / "noya_ann_canace.yaml"))   # Noya's Mark is a Cyclone
    r = simulate(gd, t, Build(), extra=[(0, _status("cyc", "hit:main:cyclone"))])
    assert r.status_time.get("cyc", 0) > 0


def test_dodges_cost_auto_time(gd, team):
    team = _bar_off(team)
    free = simulate(gd, replace(team, assumptions={**team.assumptions, "dodge_time": 0}), Build())
    paid = simulate(gd, team, Build())   # default: 10 frames per dodge, one every 10 s
    assert paid.by_slot[(0, "auto")] < free.by_slot[(0, "auto")]


def test_dodge_spam_only_with_its_potentials(gd):
    t = _bar_off(load_team(gd, TEAMS / "chitose_freesia_teresa.yaml"))   # dodge_spam: 3 s with Waltz of Ripples
    st = lambda b: simulate(gd, t, b, extra=[(0, _status("dodged", "dodge:main", 0.05))]).status_time["dodged"]
    slow, fast = st(Build()), st(Build().with_potential(144, 514411, 1))
    assert fast > 2.5 * slow


def test_dodges_wait_for_control(gd, team):
    # FL Noya's skill locks autos for 5 s: no dodge may start inside a lock
    team = replace(_bar_off(team), assumptions={**team.assumptions, "dodge_interval": 3})
    r = simulate(gd, team, Build(), extra=[(0, _status("dodged", "dodge:main", 0.05))])
    assert r.status_time["dodged"] > 0


def test_nanoha_dodge_cancels_every_string(gd):
    t = _bar_off(load_team(gd, TEAMS / "nanoha_ann_canace.yaml"))   # auto: dodge_cancel {at: 1.4, duration: 2.0}
    st = _status("dodged", "dodge:main", 1.0)
    off = simulate(gd, replace(t, assumptions={**t.assumptions, "dodge_cancel": False}), Build(), extra=[(0, st)])
    on = simulate(gd, t, Build(), extra=[(0, st)])
    assert on.status_time["dodged"] > 3 * off.status_time["dodged"]
    assert on.casts[(0, "auto")] > off.casts[(0, "auto")] and on.total > off.total


def test_chitose_tremble_and_fall_dodge_loop(gd):
    """Tremble and Fall replaces her auto string with dodge -> last strike loops (0.967 s each, user-timed)."""
    t = _bar_off(load_team(gd, TEAMS / "chitose_freesia_teresa.yaml"))
    base = simulate(gd, t, Build())
    loop = simulate(gd, t, Build().with_potential(144, 514405, 1), extra=[(0, _status("dodged", "dodge:main", 0.5))])
    assert loop.status_time["dodged"] / 0.5 > 100   # a dodge every loop
    assert loop.by_slot[(0, "auto")] > 2 * base.by_slot[(0, "auto")]
