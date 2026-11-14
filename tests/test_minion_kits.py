"""Caramel's Boombox and Ann's Bubble: minion pools timed from their own clips and AI rows; timer reactions,
reactions from several potentials, a proc chance from a potential param."""
from collections import Counter
from pathlib import Path

import pytest
from ssr.kit import SPECS, load_kit, resolve_potential
from ssr.sim import simulate
from ssr.team import Build, load_team

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

CARAMEL, ANN = 147, 123
FALLEN_DUET, MAXIMUM_BOOST = 514708, 514712
WIND_CHIME = 512307
FALL, PULSE, DUET, CABLE = 147300001, 147300002, 147300004, 147300005
SPIT, BURST = 123310001, 123310004


def _hits(gd, team, build=Build()):
    from ssr import sim as S
    seen = []
    orig = S.hit_damage
    S.hit_damage = lambda hd, *a, **k: (seen.append(hd.id) or orig(hd, *a, **k))
    try:
        r = simulate(gd, team, build)
    finally:
        S.hit_damage = orig
    return Counter(seen), r


@pytest.fixture(scope="module")
def cac(gd):
    return load_team(gd, TEAMS / "caramel_ann_canace.yaml")


@pytest.fixture(scope="module")
def anc(gd):
    return load_team(gd, TEAMS / "ann_noya_canace.yaml")


def test_boombox_falls_then_pulses_once_a_second(gd, cac):
    n, r = _hits(gd, cac)
    up = r.status_time["boombox"]
    assert n[FALL] == r.casts[(0, "skill")]          # one fall per summon
    # a pulse a second, minus the 1.433 s windup after each summon (one Boombox: a new one replaces the old)
    assert up - 1.433 * n[FALL] - n[FALL] <= n[PULSE] <= up - 1.433 * n[FALL] + n[FALL]
    assert r.by_slot[(0, "minion")] > 0


def test_timer_reaction_and_two_potentials_reactions(gd, cac):
    b = Build().with_potential(CARAMEL, FALLEN_DUET, 6).with_potential(CARAMEL, MAXIMUM_BOOST, 6)
    n, r = _hits(gd, cac, b)
    up = r.status_time["boombox"]
    assert abs(n[CABLE] - 2 * up) <= r.casts[(0, "skill")] + 2   # timer:0.5 while a Boombox is out
    assert n[DUET] == 13 * r.casts[(0, "ult")]                      # both potentials' reactions kept
    n0, _ = _hits(gd, cac)
    assert n0[CABLE] == n0[DUET] == 0


def test_bubble_spits_and_wind_chime_chance(gd, anc):
    n, r = _hits(gd, anc)
    assert n[SPIT] > 300   # a spit every 0.433 s for ~169 s of Bubble
    kit = load_kit(gd, SPECS / f"{ANN}.yaml", "main")
    rp = resolve_potential(gd, kit, WIND_CHIME, 6)
    assert rp.procs[0].chance == pytest.approx(0.25 + 0.21)   # 25% + Param1 (21% at level 6)
    # chance procs are expected values (every event lands, scaled by its chance): compare damage, not counts
    assert simulate(gd, anc, Build().with_potential(ANN, WIND_CHIME, 6)).total > r.total
