import copy
from dataclasses import replace

import pytest
import yaml

from ssr.emblems import EmblemLine, EmblemPotentialLevel, EmblemSkillLevel
from ssr.sim import simulate
from ssr.team import TEAMS, Build, TeamDocError, load_team, save_team, team_build, team_from_doc

AFC = TEAMS / "amber_flora_chixia.yaml"


@pytest.fixture
def doc():
    return yaml.safe_load(AFC.read_text())


@pytest.mark.parametrize("path", sorted(TEAMS.glob("*.yaml")), ids=lambda p: p.stem)
def test_existing_team_files_round_trip(gd, path, tmp_path):
    doc = yaml.safe_load(path.read_text())
    out = tmp_path / path.name
    save_team(doc, out)
    a, b = load_team(gd, path), load_team(gd, out)
    a, b = replace(a, fight_length=20), replace(b, fight_length=20)
    assert simulate(gd, a, Build()).total == simulate(gd, b, Build()).total
    assert yaml.safe_load(out.read_text()) == doc


def test_save_keeps_header_comments(tmp_path, doc):
    out = tmp_path / "t.yaml"
    out.write_text(AFC.read_text())
    save_team(doc, out)
    text = out.read_text()
    assert text.startswith("# Amber (main) + Flora + Chixia")
    assert "# Flora 4 s per skill" in text and yaml.safe_load(text) == doc


def test_save_new_file_has_no_header(tmp_path, doc):
    out = tmp_path / "new.yaml"
    save_team(doc, out)
    assert not out.read_text().startswith("#")


def test_targets_become_build(gd, doc):
    p = gd.table("CharPotential")["103"]["MasterNormalPotentialIds"][0]
    doc["members"][0]["targets"] = {gd.item_name(p): 4, gd.item_name(p + 1): 0}
    team = team_from_doc(gd, doc)
    assert team.members[0].targets == {p: 4, p + 1: 0}
    assert team_build(team).potentials == {(103, p): 4}


def test_slotted_emblems_parse_with_tiers(gd, doc):
    doc["members"][0]["emblems"] = [
        {"slot": 1, "lines": [{"line": "ATK%", "tier": "blue"}]},
        {"slot": 2, "lines": [{"line": "Main Skill Level Up", "tier": "+2"}]},
        {"slot": 3, "lines": [{"line": "Ardent Trigger", "tier": "+3"}]},
    ]
    m = team_from_doc(gd, doc).members[0]
    atk, skill, pot = m.emblems
    assert isinstance(atk, EmblemLine) and atk.value == pytest.approx(0.05)
    assert isinstance(skill, EmblemSkillLevel) and skill.plus == 2
    assert isinstance(pot, EmblemPotentialLevel) and pot.plus == 3 and gd.item_name(pot.potential_id) == "Ardent Trigger"
    assert m.emblem_slots == [[("ATK%", "blue")], [("Main Skill Level Up", "+2")], [("Ardent Trigger", "+3")]]


def test_legacy_flat_emblems_still_load(gd, doc):
    doc["members"][0]["emblems"] = ["ATK%", "Skill +3"]
    m = team_from_doc(gd, doc).members[0]
    assert m.emblems[0].value == pytest.approx(0.12) and m.emblems[1].plus == 3 and m.emblem_slots == []


def test_budget_and_max_level(gd, doc):
    team = team_from_doc(gd, doc)
    assert team.budget == [30, 15, 15] and team.max_level == 6
    doc["budget"], doc["max_level"] = [10, 5, 5], 4
    team = team_from_doc(gd, doc)
    assert team.budget == [10, 5, 5] and team.max_level == 4


@pytest.mark.parametrize("edit, bad", [
    (lambda d: d["members"][0].update(targets={"Nope": 3}), "Nope"),
    (lambda d: d["members"][0].update(targets={"Ardent Trigger": 9}), "9"),
    (lambda d: d["members"][1].update(emblems=[{"slot": 1, "lines": [{"line": "Bogus", "tier": "purple"}]}]), "Bogus"),
    (lambda d: d["members"][0].update(emblems=[{"slot": 1, "lines": [{"line": "Main Skill Level Up", "tier": "+1"}]}]),
     "Main Skill Level Up"),
    (lambda d: d["members"][0].update(emblems=[{"slot": 1, "lines": [{"line": "ATK%", "tier": "pink"}]}]), "pink"),
    (lambda d: d["members"][0].update(emblems=[{"slot": 1, "lines": [{"line": "ATK%", "tier": "blue"}] * 5}]), "4"),
    (lambda d: d["members"][0].update(trekker="Nobody"), "Nobody"),
    (lambda d: d["members"][0].update(pinks=["Not A Pink"]), "Not A Pink"),
    (lambda d: d["discs"]["main"].__setitem__(0, {"name": "No Such Disc"}), "No Such Disc"),
])
def test_bad_names_raise_team_doc_error(gd, doc, edit, bad):
    d = copy.deepcopy(doc)
    edit(d)
    with pytest.raises(TeamDocError, match=bad):
        team_from_doc(gd, d)
