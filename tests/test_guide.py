from collections import Counter
from dataclasses import replace

import pytest

from ssr.compare import greedy_build
from ssr.guide import emblem_table, optimize, potential_grid, rank_pinks
from ssr.rate import gain
from ssr.sim import simulate
from ssr.team import TEAMS, Build, load_team

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"   # frozen team files: the build page saves over teams/


@pytest.fixture(scope="module")
def short_team(gd):
    return replace(load_team(gd, FIXTURES / "amber_flora_chixia.yaml"), fight_length=20)


def test_grid_current_level_is_zero_and_signs(gd, short_team):
    p = gd.table("CharPotential")["103"]["MasterNormalPotentialIds"][0]
    build = Build({(103, p): 3})
    grid = potential_grid(gd, short_team, build, members=[0])
    assert {k[0] for k in grid} == {0} and len(grid) == 12
    cells = grid[(0, p)]
    assert len(cells) == 6 and cells[2] == 0.0
    base = simulate(gd, short_team, build)
    assert cells[3] == pytest.approx(gain(base, simulate(gd, short_team, Build({(103, p): 4}))))
    assert cells[0] == pytest.approx(gain(base, simulate(gd, short_team, Build({(103, p): 1}))))
    assert cells[0] < 0 < cells[5]


def test_grid_level_zero_target(gd, short_team):
    p = gd.table("CharPotential")["103"]["MasterNormalPotentialIds"][0]
    cells = potential_grid(gd, short_team, Build(), members=[0])[(0, p)]
    assert all(c > 0 for c in cells)   # nothing at 0; every level adds


def test_emblem_table_tiers_and_irrelevant_rows(gd, short_team):
    rows = emblem_table(gd, short_team, Build(), member=1)        # Flora, support
    atk = next(r for r in rows if r.name == "ATK%")
    assert [t[1] for t in atk.tiers] == ["green", "blue", "yellow", "purple"] and atk.tiers[3][2] > atk.tiers[0][2] > 0
    assert atk.slots == [1, 2, 3] and atk.relevant
    irrelevant_pots = [r for r in rows if r.kind == "potential" and not r.relevant]
    assert irrelevant_pots and all(t[2] == 0.0 for r in irrelevant_pots for t in r.tiers)
    tops = [r.tiers[-1][2] for r in rows]
    assert tops == sorted(tops, reverse=True)


def test_rank_pinks_keeps_discs(gd, short_team):
    rows = rank_pinks(gd, short_team, member=2)
    assert len(rows) == 6 and all(r.own_discs == list(short_team.discs_main) for r in rows)
    assert [r.total_team_discs for r in rows] == sorted((r.total_team_discs for r in rows), reverse=True)


def test_optimize_respects_split_and_is_at_least_greedy(gd, short_team):
    r = optimize(gd, short_team, [3, 1, 1], max_level=2)
    per = Counter()
    for (cid, _p), lv in r.build.potentials.items():
        per[cid] += lv
    assert dict(per) == {103: 3, 126: 1, 141: 1}
    assert max(r.build.potentials.values()) <= 2
    assert r.total >= greedy_build(gd, short_team, max_level=2, split=[3, 1, 1]).totals[-1]
    assert r.total == pytest.approx(simulate(gd, short_team, r.build).total)
    assert r.method.startswith("greedy") and r.base_total < r.total


def test_progress_reports_and_can_cancel(gd, short_team):
    seen = []
    potential_grid(gd, short_team, Build(), members=[2], progress=lambda *a: seen.append(a))
    assert seen and seen[-1][1] == seen[-1][2] and all(a[0] == "potentials" for a in seen)

    def boom(*_):
        raise RuntimeError("cancelled")
    with pytest.raises(RuntimeError):
        potential_grid(gd, short_team, Build(), members=[0], progress=boom)


def test_emblem_table_stat_lines_stack_per_slot(gd, short_team):
    from ssr.emblems import find_emblem_tier
    from ssr.sim import simulate
    from ssr.rate import gain
    rows = emblem_table(gd, short_team, Build(), member=1)
    atk = next(r for r in rows if r.name == "ATK%")
    assert sorted(atk.by_slot) == [1, 2, 3] and [t[2] for t in atk.tiers] == atk.by_slot[1]
    line = find_emblem_tier(gd, short_team.members[1].char_id, "ATK%", "purple").line
    one = simulate(gd, short_team, Build(), extra=[(1, line)])
    two = simulate(gd, short_team, Build(), extra=[(1, line)] * 2)
    assert abs(atk.by_slot[2][-1] - gain(one, two)) < 1e-12   # Lv80 = 2nd copy on top of the Lv70 one
    assert atk.by_slot[3][-1] > 0
    skill = next(r for r in rows if r.kind == "skill")
    assert list(skill.by_slot) == [2]


def test_optimize_total_with_caps(gd, short_team):
    r = optimize(gd, short_team, [3, 3, 3], max_level=2, total=4)
    per = Counter()
    for (cid, _p), lv in r.build.potentials.items():
        per[cid] += lv
    assert sum(per.values()) == 4 and all(v <= 3 for v in per.values())
    assert r.total >= greedy_build(gd, short_team, max_level=2, split=[3, 3, 3], total=4).totals[-1]
