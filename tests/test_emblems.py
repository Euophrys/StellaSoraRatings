from dataclasses import replace

import pytest

from ssr.emblems import EmblemChargeEfficiency, EmblemPotentialLevel, emblem_options, find_emblem_tier, line_relevant
from ssr.sim import simulate
from ssr.team import TEAMS, Build, load_team

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"   # frozen team files: the build page saves over teams/


@pytest.fixture(scope="module")
def afc(gd):
    return load_team(gd, FIXTURES / "amber_flora_chixia.yaml")


def test_stat_line_has_four_coloured_tiers(gd):
    opt = next(o for o in emblem_options(gd, 103) if o.name == "ATK%")
    assert opt.kind == "stat" and opt.slots == frozenset({1, 2, 3})
    assert [t.colour for t in opt.tiers] == ["green", "blue", "yellow", "purple"]
    assert [t.label for t in opt.tiers] == ["green", "blue", "yellow", "purple"]
    assert [round(t.line.value, 2) for t in opt.tiers] == [0.04, 0.05, 0.06, 0.12]


def test_element_lines_only_own_element(gd):
    names = {o.name for o in emblem_options(gd, 103)}       # Amber is Ignis
    assert any("Ignis" in n for n in names) and not any("Aqua" in n for n in names)


def test_option_names_are_unique(gd):
    names = [o.name for o in emblem_options(gd, 103)]
    assert len(names) == len(set(names))


def test_charge_efficiency_lines(gd):
    opts = {o.name: o for o in emblem_options(gd, 103)}
    main = opts["Charge Efficiency (Main)"]
    assert [round(t.line.value, 3) for t in main.tiers] == [0.1, 0.125, 0.15, 0.3] and main.tiers[0].line.role == "main"
    sup = opts["Charge Efficiency (Support)"]
    assert [round(t.line.value, 3) for t in sup.tiers] == [0.135, 0.17, 0.203, 0.4] and sup.tiers[0].line.role == "support"


def test_charge_efficiency_main_casts_more_ults(gd, afc):
    team = afc   # 120 s: at 60 s the earlier ult shifts the rotation without adding a cast
    base = simulate(gd, team, Build())
    main_line = EmblemChargeEfficiency("Charge Efficiency (Main)", "main", 0.3)
    sup_line = EmblemChargeEfficiency("Charge Efficiency (Support)", "support", 0.4)
    with_main = simulate(gd, team, Build(), extra=[(0, main_line)])
    assert with_main.casts[(0, "ult")] > base.casts[(0, "ult")] and with_main.total > base.total
    assert simulate(gd, team, Build(), extra=[(0, sup_line)]).total == base.total
    assert not line_relevant(sup_line, 2, "main") and line_relevant(main_line, 2, "main")


def test_skill_line_tiers(gd):
    opt = next(o for o in emblem_options(gd, 103) if o.name == "Main Skill Level Up")
    assert opt.kind == "skill" and opt.slots == frozenset({2})
    assert [(t.label, t.colour) for t in opt.tiers] == [("+1", "yellow"), ("+2", "purple"), ("+3", "purple")]
    assert [t.line.plus for t in opt.tiers] == [1, 2, 3] and opt.tiers[0].line.slot == "main_skill"


def test_potential_lines_are_the_trekkers_own(gd):
    pots = [o for o in emblem_options(gd, 103) if o.kind == "potential"]
    cp = gd.table("CharPotential")["103"]
    own = set(cp["MasterNormalPotentialIds"] + cp["AssistNormalPotentialIds"] + cp["CommonPotentialIds"])
    assert len(pots) == 21 and {o.tiers[0].line.potential_id for o in pots} == own
    assert all(o.slots == frozenset({3}) for o in pots)
    ardent = next(o for o in pots if o.name == "Ardent Trigger")
    assert [t.label for t in ardent.tiers] == ["+1", "+2", "+3"]


def test_potential_line_relevance_follows_role(gd):
    cp = gd.table("CharPotential")["103"]
    main_pot = EmblemPotentialLevel("x", cp["MasterNormalPotentialIds"][0], 3)
    assert line_relevant(main_pot, 2, "main") and not line_relevant(main_pot, 2, "support")


def test_find_emblem_tier(gd):
    t = find_emblem_tier(gd, 103, "ATK%", "blue")
    assert t.line.value == pytest.approx(0.05)
    with pytest.raises(KeyError, match="Bogus"):
        find_emblem_tier(gd, 103, "Bogus", "purple")
    with pytest.raises(KeyError, match="pink"):
        find_emblem_tier(gd, 103, "ATK%", "pink")


def test_potential_plus_raises_fight_level_and_target_zero_still_counts(gd, afc):
    team = replace(afc, fight_length=20)
    p = gd.table("CharPotential")["103"]["MasterNormalPotentialIds"][0]
    line = EmblemPotentialLevel(gd.item_name(p), p, 3)
    with_line = simulate(gd, team, Build({(103, p): 2}), extra=[(0, line)]).total
    assert with_line == pytest.approx(simulate(gd, team, Build({(103, p): 5})).total)
    assert simulate(gd, team, Build(), extra=[(0, line)]).total == pytest.approx(
        simulate(gd, team, Build({(103, p): 3})).total)


def test_potential_plus_capped_at_9(gd, afc):
    team = replace(afc, fight_length=20)
    p = gd.table("CharPotential")["103"]["MasterNormalPotentialIds"][0]
    line = EmblemPotentialLevel(gd.item_name(p), p, 3)
    assert simulate(gd, team, Build({(103, p): 8}), extra=[(0, line)]).total == pytest.approx(
        simulate(gd, team, Build({(103, p): 9})).total)


def test_owned_potential_line_applies(gd, afc):
    team = replace(afc, fight_length=20)
    p = gd.table("CharPotential")["103"]["MasterNormalPotentialIds"][0]
    members = list(team.members)
    members[0] = replace(members[0], emblems=[EmblemPotentialLevel(gd.item_name(p), p, 2)])
    owned = replace(team, members=members)
    assert simulate(gd, owned, Build({(103, p): 1})).total == pytest.approx(
        simulate(gd, team, Build({(103, p): 3})).total)
    assert simulate(gd, owned, Build({(103, p): 1}), emblems=False).total == pytest.approx(
        simulate(gd, team, Build({(103, p): 1})).total)
