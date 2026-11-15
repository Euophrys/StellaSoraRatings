"""Event and status plumbing: shared status names, event suffixes everywhere, ICDs on tick boundaries, queued
minion hits."""
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import ssr.sim as sim
from ssr.effects import Modifier, Trigger
from ssr.kit import HitSpec, ResolvedPotential
from ssr.sim import _Fight, _Mod, simulate
from ssr.team import Build, load_team

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it


def _bar_off(team):
    return replace(team, enemy=replace(team.enemy, resilience=0))


def _status(name, event, duration=1.0, icd=0.0):
    return Modifier(stat=0, value=0, target="main", name=name, source="test",
                    trigger=Trigger(event=event, duration=duration, icd=icd))


def _procs(*procs):
    return ResolvedPotential(potential_id=-1, level=1, modifiers=[], notes=[], add_hits={}, replace_hits={},
                             add_actions={}, mark_tags=(), extra_casts={}, reset_cd={}, cd_reduce=None,
                             procs=list(procs))


def test_status_from_several_buffs_counts_all_of_them(gd, team):
    """Two buffs giving one status (Teresa's Surging Shield from her skill and from squadmates' casts): it's up
    whenever either source has it, not only while the last one defined does."""
    team = _bar_off(team)
    a, b = _status("s", "timer:20"), _status("s", "timer:30")
    only_a = simulate(gd, team, Build(), extra=[(0, a)]).status_time["s"]
    only_b = simulate(gd, team, Build(), extra=[(0, b)]).status_time["s"]
    both = simulate(gd, team, Build(), extra=[(0, a), (0, b)]).status_time["s"]
    shared = len(set(range(0, int(team.fight_length), 20)) & set(range(0, int(team.fight_length), 30)))
    assert both == pytest.approx(only_a + only_b - shared, abs=0.2)


def test_once_is_kept_until_the_trigger_fires(gd, team):
    """`&once&while:`: matches while the condition is off don't use up the once (timer:10 at 0, 10, 20 miss the
    gate; at 30 the gate, up 25-31, lets it through)."""
    team = _bar_off(team)
    gate = _status("gate", "timer:25", duration=6.0)
    once = _status("once", "timer:10&while:status:gate&once", duration=2.0)
    r = simulate(gd, team, Build(), extra=[(0, gate), (0, once)])
    assert r.status_time["once"] == pytest.approx(2.0, abs=0.1)


def test_recent_combines_with_another_suffix(gd, team):
    once = _status("once", "damage:main&recent:skill_dmg:5&once", duration=2.0)
    r = simulate(gd, team, Build(), extra=[(0, once)])
    assert r.status_time["once"] == pytest.approx(2.0, abs=0.1)


def test_unknown_event_suffix_is_an_error(gd, team):
    with pytest.raises(ValueError, match="unknown suffix"):
        simulate(gd, team, Build(), extra=[(0, _status("x", "damage:main&sometimes"))])


def test_proc_event_takes_while_suffix(gd, team):
    team = _bar_off(team)
    gate = _status("gate", "timer:25", duration=7.0)
    seen = _status("pinged", "marker:main:ping")

    def pinged(event):
        p = HitSpec(hit_id=0, tags=("ping",), event=event)
        return simulate(gd, team, Build(), extra=[(0, gate), (0, seen), (0, _procs(p))]).status_time.get("pinged", 0)
    free, gated = pinged("timer:10"), pinged("timer:10&while:status:gate")
    assert 0 < gated < free


def test_conditions_take_support_and_any(gd, team):
    team = _bar_off(team)

    def up(who):
        r = simulate(gd, team, Build(), extra=[(0, _status("s", f"timer:1&while:cast_within:{who}:skill:2"))])
        return r.status_time.get("s", 0)
    s1, s2, sup, anyone = up(1), up(2), up("support"), up("any")
    assert sup >= max(s1, s2) > 0
    assert anyone >= sup


def test_icd_ends_on_the_tick_it_should():
    """step * dt arithmetic leaves t - last a hair under the ICD; the activation still counts."""
    dt, icd = 0.05, 0.3
    s0 = next(s for s in range(1000) if (s + 6) * dt - s * dt < icd)
    md = _Mod(_status("s", "x", icd=icd), 0, [0], event="x")
    fight = SimpleNamespace(refresh_stacks=True)
    assert _Fight.activate(fight, md, s0 * dt)
    assert not _Fight.activate(fight, md, (s0 + 5) * dt)
    assert _Fight.activate(fight, md, (s0 + 6) * dt)


def test_minion_hits_land_in_order_and_within_the_fight(gd, monkeypatch):
    """A minion attack with several hits queues them: none land early (out of order) or after the fight's end."""
    team = load_team(gd, TEAMS / "nanoha_ann_canace.yaml")
    times = []
    land = _Fight.land

    def spy(self, t, mi, h, action, cid):
        if action == "minion":
            times.append(t)
        return land(self, t, mi, h, action, cid)
    monkeypatch.setattr(sim._Fight, "land", spy)
    simulate(gd, team, Build())
    assert times and times == sorted(times)
    assert max(times) <= team.fight_length + 1e-9
