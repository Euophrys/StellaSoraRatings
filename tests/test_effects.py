import pytest
from ssr.effects import disc_modifiers, potential_modifiers, effect_modifiers, once_attr_modifiers
from ssr.stats import elem_stat, ELEM_DMG_BASE, ELEM_TAKEN_BASE, SKILL_DMG, SKILL_CRIT_RATE, HP, ATK


def test_ripples_melody(gd):
    mods, _ = disc_modifiers(gd, 214038, copies=1)
    lux = [m for m in mods if m.stat == elem_stat(ELEM_DMG_BASE, 5) and m.trigger is None]
    assert lux and lux[0].value == pytest.approx(0.15)
    mods6, _ = disc_modifiers(gd, 214038, copies=6)
    assert any(m.value == pytest.approx(0.30) for m in mods6 if m.stat == lux[0].stat and m.trigger is None)


def test_ripples_triggered_buff_flagged(gd):
    mods, _ = disc_modifiers(gd, 214038, copies=1)
    trig = [m for m in mods if m.trigger is not None]
    assert trig and all(m.assumed for m in trig) and trig[0].trigger.max_stacks == 9 and trig[0].trigger.duration == 15
    assert trig[0].stat == elem_stat(ELEM_TAKEN_BASE, 5) and trig[0].target == "enemy"


def test_noya_skill_dmg_potential(gd):
    mods, _ = potential_modifiers(gd, 516241, 6)
    assert any(m.stat == SKILL_DMG and m.value == pytest.approx(0.60) and m.trigger is None for m in mods)


def test_undecodable_effect_is_noted(gd):  # Review Focus 2
    mods, notes = potential_modifiers(gd, 516224, 1)   # "10 more longsword attacks" – no stat
    assert mods == [] and notes


def test_flat_vs_pct(gd):
    mods, _ = potential_modifiers(gd, 516213, 1)  # Veteran's Grit: HP +2250 flat (EffectId, second subtype 1)
    assert len(mods) == 1 and mods[0].stat == HP and not mods[0].is_pct and mods[0].value == 2250


def test_once_attr_is_scoped_hint(gd):
    mods, _ = potential_modifiers(gd, 516205, 1)  # Prism Warp: Skill Crit Rate on longsword+glow hits
    m = [m for m in mods if m.stat == SKILL_CRIT_RATE]
    assert m and m[0].value == pytest.approx(0.037) and m[0].needs_scope


def test_buffed_potential_effect_gets_trigger(gd):
    mods, _ = potential_modifiers(gd, 516207, 1)  # Lucent Tide: buff on skill cast, 12 s, 2 stacks
    assert mods and all(m.trigger is not None for m in mods)
    assert mods[0].trigger.duration == 12 and mods[0].trigger.max_stacks == 2 and mods[0].assumed


def test_permanent_stacking_buff(gd):
    import math
    mods, _ = potential_modifiers(gd, 516212, 1)  # Astral Brilliance: buff Time -1 (permanent), 3 stacks (one per Lux Trekker)
    assert mods and mods[0].assumed and math.isinf(mods[0].trigger.duration) and mods[0].trigger.max_stacks == 3


def test_script_only_effect_noted(gd):
    mods, notes = potential_modifiers(gd, 510301, 1)  # Dominant Firepower: NoLevel EffectValue applied by script
    assert mods and all(m.assumed for m in mods) and notes


def test_every_potential_interprets_without_crash(gd):  # Review Focus 1/2
    for k in gd.table("Potential"):
        for lv in (1, 9):
            potential_modifiers(gd, int(k), lv)
