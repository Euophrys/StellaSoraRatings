"""Talents (dupes), `&once` events, and supports that trigger Marks (Shia)."""
import math
from dataclasses import replace

import pytest
import yaml

from ssr.data import GameData, REPO_ROOT
from ssr.effects import Modifier, Trigger
from ssr.game import talent_groups, talent_nodes
from ssr.kit import BuffSpec, load_kit, resolve_buffs
from ssr.refs import resolve
from ssr.sim import simulate
from ssr.stats import DMG_MULT, SKILL_DMG
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it


@pytest.fixture(scope="module")
def gd():
    return GameData()


@pytest.fixture(scope="module")
def shia_team(gd):
    return load_team(gd, TEAMS / "fl_noya_t1_shia_tilia.yaml")


def test_talent_groups_in_unlock_order(gd):
    groups = talent_groups(gd, 162)
    assert [g["Id"] for g in groups] == [16201, 16202, 16203, 16204, 16205]


def test_talent_nodes_t1(gd):
    effects, keys = talent_nodes(gd, 162, 1)
    assert len(effects) == 10 and keys == [1620116]   # 10 stat nodes + Buried Past
    assert talent_nodes(gd, 162, 0) == ([], [])


def test_t1_starender_from_first_hit(gd, shia_team):
    t1 = simulate(gd, shia_team, Build())
    m0 = replace(shia_team.members[0], talents=0)
    t0 = simulate(gd, replace(shia_team, members=[m0] + shia_team.members[1:]), Build())
    # T0: Starender only from the ults x 30 s (2 ults since passive energy was removed); T1: from the first hit as well
    n = t0.casts[(0, "ult")]
    assert n == 2 and t0.status_time["starender"] == pytest.approx(30 * n, abs=1.5)
    assert t1.status_time["starender"] > t0.status_time["starender"] + 25   # +30 s from the first hit
    assert t1.total > t0.total
    assert not any("key talent" in u for u in t1.unknown_modifiers)


def test_single_row_talent_buff_ignores_the_skill_level(gd, shia_team):
    """Buried Past's row is one id: at ult Lv10, id + 100 is a different talent's row (stat 85, 36%)."""
    kit = shia_team.members[0].kit
    mods = resolve_buffs(gd, kit, {"ult": 10, "skill": 10}, set(), kit.talents[1620116].buffs)
    assert [(m.stat, m.value) for m in mods] == [(8, pytest.approx(0.12))]   # Crit DMG +12%


def test_once_event_fires_once(gd, shia_team):
    # without ults, a T1 Noya gets exactly one 30 s Starender (from her first hit)
    m0 = shia_team.members[0]
    kit = replace(m0.kit, actions={k: v for k, v in m0.kit.actions.items() if k != "ult"})
    team = replace(shia_team, members=[replace(m0, kit=kit)] + shia_team.members[1:])
    r = simulate(gd, team, Build())
    assert r.status_time["starender"] == pytest.approx(30, abs=0.2)


def test_support_triggers_marks(gd, shia_team):
    r = simulate(gd, shia_team, Build())
    assert r.by_slot.get((1, "mark"), 0) > 0      # Shia's Thunderbolt
    assert r.by_slot.get((0, "mark"), 0) > 0      # Noya still gets some Marks


# ---- every key talent of every Trekker

SPECS = sorted((REPO_ROOT / "specs" / "trekkers").glob("*.yaml"))
NOT_MODELLED = {1230348, 1580464}   # needs a hostile projectile; needs Dame Laru's shield (docs/assumptions.md)


def _key_talents(gd, path):
    cid = int(path.stem)
    return [r for g in talent_groups(gd, cid) for r in gd.table("Talent").values()
            if r.get("GroupId") == g["Id"] and r.get("Type") == 1]


def _kit(gd, path):
    return load_kit(gd, path, "support" if "support" in yaml.safe_load(path.read_text()) else "main")


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.stem)
def test_every_key_talent_has_an_entry(gd, path):
    kit = _kit(gd, path)
    assert {r["Id"] for r in _key_talents(gd, path)} - set(kit.talents) <= NOT_MODELLED


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.stem)
def test_talent_numbers_are_the_talents_own(gd, path):
    """Each number the talent's text shows is its modifier's value, duration, stack cap or ICD."""
    kit = _kit(gd, path)
    for row in _key_talents(gd, path):
        ts = kit.talents.get(row["Id"])
        if ts is None or not ts.buffs:
            continue
        seen = set()
        for m in resolve_buffs(gd, kit, {}, set(), ts.buffs):
            seen.add(round(m.value, 6))
            if m.trigger:
                seen |= {round(float(m.trigger.duration), 6), m.trigger.max_stacks, round(m.trigger.icd, 6), m.trigger.every}
        for k, ref in row.items():
            if k.startswith("Param") and ref.split(",")[2:3] != [""]:   # empty placeholders (Leader's Duty Param3)
                assert round(float(resolve(gd, ref, 1).value), 6) in seen, f"{row['Id']} {k} {ref}"


def test_talents_apply_to_both_roles(gd):
    path = REPO_ROOT / "specs" / "trekkers" / "107.yaml"
    assert set(load_kit(gd, path, "main").talents) == set(load_kit(gd, path, "support").talents) != set()


def test_talent_tiers_add_damage_and_list_what_is_missing(gd):
    team = load_team(gd, TEAMS / "nanoha_ann_tilia.yaml")
    totals = []
    for tier in range(6):
        r = simulate(gd, replace(team, members=[replace(m, talents=tier) for m in team.members]), Build())
        totals.append(r.total)
    assert totals == sorted(totals) and totals[5] > totals[0]
    assert [u for u in r.unknown_modifiers if "key talent" in u] == ["Ann key talent 1230348: not in the kit spec, not modelled"]


# ---- what the talents added to the engine

def _skill_dmg(value, event, **trigger):
    return Modifier(stat=SKILL_DMG, value=value, source="test", trigger=Trigger(event=event, duration=math.inf, **trigger))


def test_damage_event_fires_once_per_hit(gd, shia_team):
    """`damage:<who>` = one bucket event per hit, while `hit:<who>:any` also fires for each tag."""
    def total(event):
        m = _skill_dmg(1e-4, event, max_stacks=100000)
        return simulate(gd, shia_team, Build(), extra=[(0, m)]).total
    buckets = "|".join(f"hit:0:{s}_dmg" for s in ("auto", "skill", "ult", "other", "mark", "minion"))
    assert total("damage:0") == pytest.approx(total(buckets), rel=1e-12)
    assert total("damage:0") < total("hit:0:any")


def test_squad_condition(gd, shia_team):
    all_lux = shia_team
    mixed = load_team(gd, TEAMS / "nanoha_ann_tilia.yaml")
    for team, gains in ((all_lux, True), (mixed, False)):
        m = _skill_dmg(1.0, "while:squad:5:3")
        base, buffed = simulate(gd, team, Build()).total, simulate(gd, team, Build(), extra=[(0, m)]).total
        assert (buffed > base) == gains


def test_mark_element_events_ignore_other_elements(gd):
    """"When Ignis Mark is triggered" doesn't fire on Mistique's Umbra Marks: `mark:element<N>`."""
    team = load_team(gd, TEAMS / "mistique_chixia_cosette.yaml")
    base = simulate(gd, team, Build()).total
    ignis = _skill_dmg(1.0, "mark:element2")
    umbra = _skill_dmg(1.0, "mark:element6")
    assert simulate(gd, team, Build(), extra=[(0, ignis)]).total == pytest.approx(base)
    assert simulate(gd, team, Build(), extra=[(0, umbra)]).total > base


def test_kit_buff_always_every_icd(gd, shia_team):
    kit = shia_team.members[0].kit
    on, every = resolve_buffs(gd, kit, {}, set(), [
        BuffSpec(effect=None, level="skill", event="always"),
        BuffSpec(effect=None, level="skill", event="cast:self:ult", every=4, icd=2, reset_on=("cast:self:skill",)),
    ])
    assert on.trigger is None
    assert (every.trigger.every, every.trigger.icd, every.trigger.reset_on) == (4, 2.0, ("cast:self:skill",))


def test_stacks_gone_after_the_ult_count_for_its_hits(gd):
    """Afterrain Clarity (Chitose T4): all of the ult's hits get the stacks, then they're cleared."""
    team = load_team(gd, TEAMS / "chitose_freesia_teresa.yaml")
    def ult(kit_edit):
        m = team.members[0]
        t = replace(team, members=[replace(m, talents=4, kit=kit_edit(m.kit))] + team.members[1:])
        return simulate(gd, t, Build()).by_slot[(0, "ult")]
    def without(tid):
        return lambda k: replace(k, talents={i: s for i, s in k.talents.items() if i != tid})
    def never_cleared(k):
        s = k.talents[1440464]
        return replace(k, talents={**k.talents, 1440464: replace(s, buffs=[replace(b, reset_on=()) for b in s.buffs])})
    assert ult(without(1440464)) < ult(lambda k: k) < ult(never_cleared)


def test_toys_status_needs_a_shell(gd):
    team = load_team(gd, TEAMS / "amber_laru_flora.yaml")
    i = next(i for i, m in enumerate(team.members) if m.char_id == 158)
    t = replace(team, members=[replace(m, talents=1 if j == i else 0) for j, m in enumerate(team.members)])
    r = simulate(gd, t, Build())
    assert 0 < r.status_time["toys"] <= team.fight_length


def test_night_watcher_multiplier_only_on_named_hits(gd, shia_team):
    kit = shia_team.members[0].kit
    mods = resolve_buffs(gd, kit, {}, set(), kit.talents[1620232].buffs)
    mult = next(m for m in mods if m.stat == DMG_MULT)
    assert mult.value == pytest.approx(0.36) and set(mult.hit_tags) == {"flurry", "starfall"}
