"""Mistique + Chixia + Cosette: minion pools, per-element Marks, restarting procs, wait_on_field, element targets."""
from dataclasses import replace

import pytest
from ssr.builds import with_pinks
from ssr.sim import _targets, simulate
from ssr.team import Build, load_team, TEAMS

MISTIQUE, CHIXIA, COSETTE = 135, 141, 142
DEFIANCE, BURST, EXTENDED, THREAD = 513501, 513502, 513503, 513504
SWIPE, HEADBUTT, EXPLOSION = 135900001, 135900002, 135900004
MARK, DARK_BURN = 135000000, 135000001


@pytest.fixture(scope="module")
def mcc(gd):
    return load_team(gd, TEAMS / "mistique_chixia_cosette.yaml")


def _hits(gd, team, build=Build()):
    from ssr import sim as S
    seen = []
    orig = S.hit_damage
    S.hit_damage = lambda hd, *a, **k: (seen.append(hd.id) or orig(hd, *a, **k))
    try:
        r = simulate(gd, team, build)
    finally:
        S.hit_damage = orig
    return seen, r


def test_phantom_windup_and_alternating_attacks(gd, mcc):
    # skill at 1.0; Phantom 1 at 1.7, attacks from 3.133 every 0.7 s (Swipe, Headbutt, ...); Phantom 2 at 4.7 -> 6.133
    seen, _ = _hits(gd, replace(mcc, fight_length=6.0))
    assert seen.count(SWIPE) == 3 and seen.count(HEADBUTT) == 2


def test_replace_oldest_vanishes_and_explodes(gd, mcc):
    # Without Extended Exposure the 5th tick replaces the oldest: explosions at 13.7 + 0.87 and 16.7 + 0.87
    team = with_pinks(replace(mcc, fight_length=20.0), 0, [DEFIANCE, THREAD])
    seen, r = _hits(gd, team)
    assert seen.count(EXPLOSION) == 2
    assert r.casts[(0, "skill")] == 3   # 11 s CD - 2 s (Defiance): 1.0, 10.0, 19.0


def test_extended_exposure_refreshes_instead(gd, mcc):
    seen, _ = _hits(gd, with_pinks(replace(mcc, fight_length=20.0), 0, [DEFIANCE, EXTENDED]))
    assert seen.count(EXPLOSION) == 0


def test_marks_are_per_element(gd, mcc):
    # Chixia's minions apply Ignis Marks: Mistique (Umbra) can't trigger them; Cosette's Gloom she can.
    seen, _ = _hits(gd, replace(mcc, fight_length=40.0, members=mcc.members[:2], hold=[]))
    assert seen.count(MARK) == 0
    seen, _ = _hits(gd, replace(mcc, fight_length=40.0))
    assert seen.count(MARK) > 0


def test_dark_burn_restarts(gd, mcc):
    # Dark Burn: 10 ticks per Mark trigger, but a new trigger replaces the running one
    seen, _ = _hits(gd, replace(mcc, fight_length=40.0))
    marks, ticks = seen.count(MARK), seen.count(DARK_BURN)
    assert marks > 1 and 0 < ticks < 10 * marks


def test_cosette_ult_waits_for_skill(gd, mcc):
    # with plenty of energy the ult is ready at once; it waits until the skill's 7.37 s on the field end
    cos = mcc.members[2]
    fast = replace(cos, kit=replace(cos.kit, energy_per_second=1000.0))
    team = replace(mcc, fight_length=12.0, members=[*mcc.members[:2], fast])
    r = simulate(gd, team, Build())
    assert r.first_cast[(2, "ult")] >= r.first_cast[(2, "skill")] + 7.36
    eager = replace(fast, kit=replace(fast.kit, wait_on_field=False))
    r = simulate(gd, replace(team, members=[*mcc.members[:2], eager]), Build())
    assert r.first_cast[(2, "ult")] < r.first_cast[(2, "skill")] + 1.0


def test_element_target():
    assert _targets("element:6", 2, 3, [2, 2, 3], [6, 2, 6]) == [0, 2]


def test_thread_the_needle_icd_per_phantom_from_summon(gd, mcc):
    # Phantom 1 summoned 1.7 s: its 2.5 s ICD ends 4.2 s; Mistique's next hit (auto at ~4.77) -> one spin (x2).
    # Phantom 2 (4.7 s) is on cooldown until 7.2 s.
    team = with_pinks(replace(mcc, fight_length=6.0), 0, [DEFIANCE, THREAD])
    seen, _ = _hits(gd, team)
    assert seen.count(135900003) == 2


def test_who_intersection_and_element_tokens():
    from ssr.sim import _expand_who
    classes, elements = [2, 2, 3], [6, 2, 6]
    assert _expand_who("cast:support/element6:skill", 3, classes, elements) == "cast:2:skill"
    assert _expand_who("hit:class2/element6:skill_dmg", 3, classes, elements) == "hit:0:skill_dmg"
    assert _expand_who("summon:element6:any", 3, classes, elements) == "summon:0:any|summon:2:any"
    assert _expand_who("mark:class3/element2", 3, classes, elements) == "never:mark"


def test_main_element_gates_disc_effects(gd):
    # Meowing Cat God: "When the main Ignis Trekker casts a skill" -> tied to an Ignis main
    from ssr.effects import disc_modifiers
    mods = disc_modifiers(gd, 214001, 1)[0]
    tied = [m for m in mods if m.main_element]
    assert {m.stat for m in tied} == {1, 58} and all(m.main_element == 2 for m in tied)
    assert all(m.main_element == 0 for m in mods if m.trigger is None)   # squad Ignis DMG stays


def test_main_element_drops_for_other_mains(gd, mcc):
    # Umbra main: Meowing Cat God gives only its always-on Ignis DMG (to Chixia)
    from ssr.team import FILLER
    meow = replace(mcc, discs_main=[(214001, 1), (FILLER, 6), (FILLER, 6)])
    from ssr import sim as S
    calls = []
    orig = S._Mod
    S._Mod = lambda m, *a, **k: (calls.append(m) or orig(m, *a, **k))
    try:
        simulate(gd, meow, Build())
    finally:
        S._Mod = orig
    assert not [m for m in calls if "Meowing" in m.source and m.main_element]


def test_weak_element_res(gd, mcc):
    # Umbra-weak boss: Umbra keeps `res` (250), other elements get `res_neutral` (750): Chixia (Ignis) loses ~47%
    from ssr.formula import Enemy, er_amend
    assert mcc.enemy.res_by_element.get(6, mcc.enemy.res) == 250 and mcc.enemy.res_by_element[2] == 750
    assert er_amend(750, 0) / er_amend(250, 0) == pytest.approx(0.533, abs=0.01)
    flat = replace(mcc, enemy=replace(mcc.enemy, res_by_element={}))
    a, b = simulate(gd, mcc, Build()), simulate(gd, flat, Build())
    assert a.by_member[0] == pytest.approx(b.by_member[0])          # Umbra main unchanged
    assert a.by_member[1] == pytest.approx(b.by_member[1] * 0.533, rel=0.02)   # Ignis Chixia


def test_hold_waits_for_condition_up_to_max_wait(gd, mcc):
    free = simulate(gd, replace(mcc, hold=[]), Build())
    t0 = free.first_cast[(0, "ult")]
    # never true (no Ventus Marks): waits exactly max_wait, then casts
    never = replace(mcc, hold=[{"member": 0, "action": "ult", "until": "while:mark:4", "max_wait": 5}])
    assert simulate(gd, never, Build()).first_cast[(0, "ult")] == pytest.approx(t0 + 5, abs=0.06)
    # a condition that already holds doesn't delay anything
    always = replace(mcc, hold=[{"member": 0, "action": "ult", "until": "while:cast_within:0:skill:999", "max_wait": 5}])
    assert simulate(gd, always, Build()).first_cast[(0, "ult")] == pytest.approx(t0)


def test_hold_only_if(gd, mcc):
    free = simulate(gd, replace(mcc, hold=[]), Build()).first_cast[(0, "ult")]
    # only_if false when the ult becomes ready (Ventus Marks never exist): fires at once, no waiting
    rule = {"member": 0, "action": "ult", "until": "while:mark:4", "max_wait": 5, "only_if": "while:mark:4"}
    assert simulate(gd, replace(mcc, hold=[rule]), Build()).first_cast[(0, "ult")] == pytest.approx(free)
    # only_if true: waits as before
    rule["only_if"] = "while:cd_within:2:skill:99"
    assert simulate(gd, replace(mcc, hold=[rule]), Build()).first_cast[(0, "ult")] == pytest.approx(free + 5, abs=0.06)
