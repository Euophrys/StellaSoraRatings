import pytest
from ssr.refs import resolve
from ssr.stats import STAT_NAMES, SKILL_DMG, elem_stat, ELEM_PEN_BASE, StatBlock, ATK, HP


def test_levelup_ref(gd):
    r = "Effect,LevelUp,16241001,EffectTypeParam1,HdPct"
    assert resolve(gd, r, 1).value == pytest.approx(0.15)
    assert resolve(gd, r, 6).value == pytest.approx(0.60)
    assert resolve(gd, r, 7).value == pytest.approx(0.66)


def test_enum_ref(gd):
    r = resolve(gd, "Effect,LevelUp,16241001,EffectTypeFirstSubtype,Enum,EAT", 1)
    assert r.is_enum and r.value == SKILL_DMG


def test_once_attr_ref_clamps(gd):  # 16205xx1 rows exist only to Lv9
    r = "OnceAdditionalAttribute,LevelUp,16205001,Value1,10KHdPct"
    assert resolve(gd, r, 1).value == pytest.approx(0.037)
    assert resolve(gd, r, 12).value == pytest.approx(0.15)


def test_nolevel_ref_ignores_level(gd):  # Review Focus 1
    r = "BuffValue,NoLevel,10350511,Time,10K"
    assert resolve(gd, r, 1).value == pytest.approx(10.0)
    assert resolve(gd, r, 9).value == pytest.approx(10.0)


def test_levelup_script_parameter(gd):
    assert resolve(gd, "ScriptParameter,LevelUp,10851001,CommonData,10K", 1).value == pytest.approx(1.0)


def test_hitdamage_ref_returns_list(gd):
    v = resolve(gd, "HitDamage,DamageNum,162100001", 1).value
    assert isinstance(v, list) and v[0] == pytest.approx(0.45)


def test_stat_names():
    assert STAT_NAMES[27] == "Lux PEN" and STAT_NAMES[64] == "Mark DMG"


def test_elem_stat():
    assert elem_stat(ELEM_PEN_BASE, 5) == 27


def test_statblock_final():
    s = StatBlock()
    s.set_base(ATK, 1000)
    s.flat[ATK] += 500
    s.pct[ATK] += 0.2
    assert s.final(ATK) == pytest.approx(1800)
    t = StatBlock(); t.flat[HP] += 10
    s.add(t)
    assert s.flat[HP] == 10


def test_levelup_ref_without_level_rows_uses_base_row(gd):  # Review Focus 1: 516204 refs 16204011 directly
    r = "OnceAdditionalAttribute,LevelUp,16204011,Value1,10KHdPct"
    assert resolve(gd, r, 1).value == pytest.approx(0.2)
    assert resolve(gd, r, 9).value == pytest.approx(0.2)


def test_levelup_ref_missing_everywhere_raises_keyerror(gd):
    with pytest.raises(KeyError):
        resolve(gd, "OnceAdditionalAttribute,LevelUp,99999990001,Value1,10K", 1)
