import pytest
from ssr.team import load_team, FILLER, Build, emblem_lines
from ssr.stats import HP, CRIT_RATE, elem_stat, ELEM_PEN_BASE


def test_team_members(gd, team):
    assert [m.char_id for m in team.members] == [162, 115, 107]
    assert team.members[0].role == "main" and team.members[1].role == "support"
    assert {gd.item_name(p) for p in team.members[0].pinks} == {"Lucent Blitz", "Dawnflare"}
    assert team.members[0].kit.actions["skill"].lock == 2.1


def test_team_discs(gd, team):
    ids = [d for d, _ in team.discs_main]
    assert ids[:2] == [214066, 214038] and gd.item_name(ids[2]).startswith("A Moment in the Aft")
    assert all(d == FILLER for d, _ in team.discs_support)


def test_enemy_and_reference(team):
    assert team.enemy.res == 250 and team.reference["steps"] == 2 and team.fight_length == 120


def test_build_is_immutable():
    b = Build()
    b2 = b.with_potential(162, 516205, 6)
    assert b.potentials == {} and b2.potentials == {(162, 516205): 6}
    assert b2.without(162, 516205).potentials == {}


def test_emblem_lines(gd):
    lines = {l.name: l for l in emblem_lines(gd)}
    assert lines["HP%"].stat == HP and lines["HP%"].is_pct and lines["HP%"].value == pytest.approx(0.12)
    assert lines["Crit Rate"].stat == CRIT_RATE and lines["Crit Rate"].value == pytest.approx(0.15)
    assert lines["Lux PEN"].stat == elem_stat(ELEM_PEN_BASE, 5) and lines["Lux PEN"].value == 110
    assert lines["Skill +3"].action == "skill" and lines["Skill +3"].plus == 3
