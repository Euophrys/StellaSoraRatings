"""Greedy equal-budget builds for cross-team comparison."""
from ssr.compare import greedy_build
from ssr.team import Build, load_team, TEAMS

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"   # frozen team files: the build page saves over teams/


def test_greedy_build_monotone_and_capped(gd):
    team = load_team(gd, FIXTURES / "amber_flora_chixia.yaml")
    r = greedy_build(gd, team, budget=3, max_level=1)
    assert len(r.picks) == 3 and len(r.build.potentials) == 3          # cap 1: three different potentials
    assert all(lv == 1 for lv in r.build.potentials.values())
    assert r.base_total < r.totals[0] <= r.totals[1] <= r.totals[2]


def test_greedy_split_respects_member_budgets(gd):
    team = load_team(gd, FIXTURES / "amber_flora_chixia.yaml")
    r = greedy_build(gd, team, max_level=6, split=[2, 0, 1])
    per = {}
    for (cid, _p), lv in r.build.potentials.items():
        per[cid] = per.get(cid, 0) + lv
    assert per.get(103, 0) == 2 and per.get(126, 0) == 0 and per.get(141, 0) == 1


def test_greedy_total_with_caps(gd):
    # shared budget of 3 with caps 2/2/2: at most 3 levels in all, no member above 2
    team = load_team(gd, FIXTURES / "amber_flora_chixia.yaml")
    r = greedy_build(gd, team, max_level=6, split=[2, 2, 2], total=3)
    per = {}
    for (cid, _p), lv in r.build.potentials.items():
        per[cid] = per.get(cid, 0) + lv
    assert sum(per.values()) == 3 and all(v <= 2 for v in per.values())


def test_greedy_emblems_respect_slots_and_gain(gd):
    from ssr.compare import greedy_emblems
    from ssr.emblems import emblem_options
    team = load_team(gd, TEAMS / "nazuna_leafia_gerie.yaml")
    e = greedy_emblems(gd, team, Build(), "purple", members=[0], per_slot=2)
    kinds = {o.name: o.kind for o in emblem_options(gd, team.members[0].char_id)}
    sl = e.slots[0]
    assert all(kinds[n] == "stat" for n, _ in sl[1])            # Lv70: stat lines only
    assert all(kinds[n] in ("stat", "skill") for n, _ in sl[2])  # Lv80: + skill levels
    assert all(kinds[n] in ("stat", "potential") for n, _ in sl[3])
    assert all(len(v) <= 2 and len({n for n, _ in v}) == len(v) for v in sl.values())   # once per emblem
    assert e.totals == sorted(e.totals) and e.totals[0] > e.base_total
