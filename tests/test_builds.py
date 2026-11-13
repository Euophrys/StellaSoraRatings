from dataclasses import replace
from pathlib import Path

from ssr.builds import pink_pairs, search_pinks, with_pinks
from ssr.team import load_team

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/


def test_six_pairs_per_member(gd, team):
    for i in range(3):
        pairs = pink_pairs(gd, team, i)
        assert len(pairs) == 6 and len(set(pairs)) == 6


def test_with_pinks_leaves_original(gd, team):
    t = with_pinks(team, 0, [516203, 516204])
    assert t.members[0].pinks == [516203, 516204]
    assert team.members[0].pinks == [516201, 516202]
    assert t.members[1] is team.members[1]


def test_search_pinks_can_keep_discs(gd):
    team = replace(load_team(gd, TEAMS / "nazuna_leafia_gerie.yaml"), fight_length=20, reference={"steps": 0},
                   discs_main=[(214067, 1), (0, 6), (0, 6)])   # a real disc: own_discs=True would re-pick it
    out, rows = search_pinks(gd, team, [0], own_discs=False)
    assert out.discs_main == team.discs_main and len(rows[0]) == 6
    assert all(r.own_discs == team.discs_main for r in rows[0])
