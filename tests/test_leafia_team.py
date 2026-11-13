"""Leafia: resources (Resource Markers) gained and spent by procs, procs that summon, `at_max: block`."""
from dataclasses import replace

import pytest
from ssr.builds import with_pinks
from ssr.sim import simulate
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

LEAFIA = 161
OVERCLOCK, PENETRATION, ECHO, ASSAULT = 516101, 516102, 516103, 516104
CO_DRAW, ITERATION = 516121, 516122
MARKER_OVERLOAD, OBSERVER_ARRAY = 516107, 516110
STRIKE, CRYSTAL, VECTOR = 161100001, 161100004, 161100007
FA_BULLET, MAPPING, VANGUARD = 161310004, 161320002, 161320001


@pytest.fixture(scope="module")
def lng(gd):
    return load_team(gd, TEAMS / "leafia_nazuna_gerie.yaml")


def _hits(gd, team, build=Build()):
    from ssr import sim as S
    seen = []
    orig = S.hit_damage
    S.hit_damage = lambda hd, *a, **k: (seen.append(hd.id) or orig(hd, *a, **k))
    try:
        r = simulate(gd, team, build)
    finally:
        S.hit_damage = orig
    return seen, r


def test_crystals_spend_markers(gd, lng):
    # Skill at 1.0 (+5 Markers at 1.883); swings from 2.2 at +0.433 / 1.0 / 1.733 / 2.533 / 3.067 / 3.867.
    # +2 Markers at most once per second (user), 3 per crystal:
    # 5 -> C(2)+2 -> C(1) -> strike(1)+2 -> C(0) -> strike(0)+2 -> strike(2): 3 crystals, 3 strikes.
    seen, _ = _hits(gd, replace(lng, fight_length=6.5))
    assert seen.count(CRYSTAL) == 3 and seen.count(STRIKE) == 3


def test_marker_overload_crystals_cost_two(gd, lng):
    # 5 -> C(3)+2 -> C(3) -> C(1)+2 -> C(1) -> strike(1)+2 -> C(1): 5 crystals, 1 strike
    seen, _ = _hits(gd, replace(lng, fight_length=6.5), Build().with_potential(LEAFIA, MARKER_OVERLOAD, 1))
    assert seen.count(CRYSTAL) == 5 and seen.count(STRIKE) == 1
    assert seen.count(VECTOR) == 5   # 80% chance: expected value, each lands at 0.8 of the hit


def test_turrets_from_skill_and_observer_array(gd, lng):
    team = with_pinks(replace(lng, fight_length=60.0), 0, [ASSAULT, ECHO])
    one, _ = _hits(gd, team)
    three, _ = _hits(gd, team, Build().with_potential(LEAFIA, OBSERVER_ARRAY, 6))   # limit 1 / 2 / 3 at Lv1 / 4 / 6
    # one turret fires ~1/s from 1.883 + 1.8, less the windups lost when a new one replaces it; Observer Array
    # Lv6 keeps up to 3 out
    assert 40 <= one.count(FA_BULLET) <= 57
    assert three.count(FA_BULLET) > 2.2 * one.count(FA_BULLET)


def test_block_keeps_the_pool_at_max(gd, lng):
    team = with_pinks(replace(lng, fight_length=60.0), 0, [ASSAULT, ECHO])
    m0 = team.members[0]
    pools = {k: replace(v, at_max="block") for k, v in m0.kit.minions.items()}
    team = replace(team, members=[replace(m0, kit=replace(m0.kit, minions=pools)), *team.members[1:]])
    seen, _ = _hits(gd, team)
    # one 30 s turret at a time, never replaced: no lost windups, at most one shot per 1.033 s
    assert seen.count(FA_BULLET) <= 60 / 1.033 + 1


def test_undeclared_resource_is_an_error(gd, lng):
    m0 = lng.members[0]
    team = replace(lng, members=[replace(m0, kit=replace(m0.kit, resources={})), *lng.members[1:]])
    with pytest.raises(ValueError, match="markers"):
        simulate(gd, replace(team, fight_length=5.0), Build())


def test_support_turrets_co_draw(gd):
    team = load_team(gd, TEAMS / "nazuna_leafia_gerie.yaml")
    seen, r = _hits(gd, replace(team, fight_length=30.0))
    # Co-Draw: 2 turrets out together, Tactical Mapping every 1.033 s each; a Vanguard Strike per summon
    casts = r.casts[(1, "skill")]
    assert seen.count(VANGUARD) == casts
    assert seen.count(MAPPING) > 1.2 * (30.0 - 3.0) / 1.033
    no_co_draw = with_pinks(team, 1, [ITERATION])
    seen1, _ = _hits(gd, replace(no_co_draw, fight_length=30.0))
    assert seen1.count(MAPPING) < seen.count(MAPPING) / 2


def test_greedy_lookahead_finds_observer_array(gd, lng):
    # Observer Array's turret limit is 1 / 2 / 3 at Lv1 / 4 / 6: one level at a time a greedy build never gets there
    from ssr.compare import greedy_build
    team = with_pinks(lng, 0, [ASSAULT, ECHO])
    r = greedy_build(gd, team, max_level=6, split=[6, 0, 0])
    assert r.build.potentials.get((LEAFIA, OBSERVER_ARRAY)) == 6
    assert len(r.totals) == 6 and r.totals == sorted(r.totals)
