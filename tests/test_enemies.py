from ssr.game import toughness_adjust
from ssr.enemies import monster_values


def test_toughness_adjust(gd):
    assert toughness_adjust(gd, 162) == 1.5   # FL Noya
    assert toughness_adjust(gd, 144) == 1.5   # Chitose
    assert toughness_adjust(gd, 103) == 1.0   # Amber
    assert toughness_adjust(gd, 135) == 1.0   # Mistique


def test_lithe_beauty_values(gd):
    v = monster_values(gd, 6310280)
    assert v["resilience"] == 250_000_000 and v["break_time"] == 10.0 and v["refill"] is True
    assert v["defense"] == 500 and v["element"] == 2 and sorted(v["weak"]) == [3, 5]
    assert v["res"] == {1: 750, 2: 2000, 3: 250, 4: 750, 5: 250, 6: 750}


def test_count_of_the_duloos_values(gd):
    v = monster_values(gd, 6310270)
    assert v["res"] == {1: 250, 2: 750, 3: 750, 4: 2000, 5: 250, 6: 750} and v["element"] == 4


from ssr.enemies import enemy_from_doc, preset_names
from ssr.team import team_from_doc, TeamDocError
import pytest
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it


def test_preset_names():
    assert preset_names() == ["generic", "count_of_the_duloos", "lithe_beauty"]


def test_lithe_beauty_preset(gd):
    e = enemy_from_doc(gd, {"preset": "lithe_beauty"})
    assert e.resilience == 250e6 and e.break_time == 10 and e.break_ratio == 1.5 and e.fight_length == 180
    assert e.res == 250 and e.res_by_element[5] == 250 and e.res_by_element[2] == 2000 and e.res_by_element[1] == 750
    vals = sorted((m.stat, m.value, m.trigger.duration, m.trigger.max_stacks) for m in e.ability)
    assert vals == [(61, pytest.approx(0.12), 15.0, 4), (65, pytest.approx(0.04), 15.0, 4)]


def test_count_preset_ability(gd):
    e = enemy_from_doc(gd, {"preset": "count_of_the_duloos"})
    skill = [m for m in e.ability if m.stat == 61][0]
    assert skill.value == pytest.approx(0.08) and skill.trigger.duration == 3.0 and skill.trigger.max_stacks == 5
    assert skill.trigger.event == "mark:main"
    assert any(m.stat == 3 and m.is_pct and m.value == pytest.approx(0.2) and m.trigger is None for m in e.ability)


def test_legacy_enemy_is_generic(gd):
    e = enemy_from_doc(gd, {"res": 250, "defense": 500, "broken": 1.0})
    assert e.name == "generic" and e.resilience == 250e6 and e.res == 250


def test_bar_off_and_overrides(gd):
    e = enemy_from_doc(gd, {"preset": "lithe_beauty", "resilience": 0, "break_ratio": 2.5})
    assert e.resilience == 0 and e.break_ratio == 2.5


def test_unknown_preset(gd):
    import yaml
    doc = yaml.safe_load(open(TEAMS / "fl_noya_skill.yaml"))
    doc["enemy"] = {"preset": "nope"}
    with pytest.raises(TeamDocError, match="lithe_beauty"):
        team_from_doc(gd, doc)


@pytest.mark.parametrize("name", ["../trekkers/142", "../../teams/fl_noya_skill", "Lithe_Beauty"])
def test_preset_must_be_a_listed_name(gd, name):
    with pytest.raises(KeyError, match="unknown enemy preset"):
        enemy_from_doc(gd, {"preset": name})
