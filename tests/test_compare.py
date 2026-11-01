"""Greedy equal-budget builds for cross-team comparison."""
from ssr.compare import greedy_build
from ssr.team import load_team, TEAMS


def test_greedy_build_monotone_and_capped(gd):
    team = load_team(gd, TEAMS / "amber_flora_chixia.yaml")
    r = greedy_build(gd, team, budget=3, max_level=1)
    assert len(r.picks) == 3 and len(r.build.potentials) == 3          # cap 1: three different potentials
    assert all(lv == 1 for lv in r.build.potentials.values())
    assert r.base_total < r.totals[0] <= r.totals[1] <= r.totals[2]


def test_greedy_split_respects_member_budgets(gd):
    team = load_team(gd, TEAMS / "amber_flora_chixia.yaml")
    r = greedy_build(gd, team, max_level=6, split=[2, 0, 1])
    per = {}
    for (cid, _p), lv in r.build.potentials.items():
        per[cid] = per.get(cid, 0) + lv
    assert per.get(103, 0) == 2 and per.get(126, 0) == 0 and per.get(141, 0) == 1
