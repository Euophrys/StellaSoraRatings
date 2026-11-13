"""ATK SPD on the main's auto string and windowed cooldown cuts (Amber's Confident Mode and Overloaded Spark)."""
from dataclasses import replace

import pytest
from ssr import sim as sim_module
from ssr.builds import with_pinks
from ssr.effects import Modifier
from ssr.kit import ResolvedPotential
from ssr.sim import simulate
from ssr.stats import ATK_SPD
from ssr.team import Build, load_team
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

AMBER = 103
PTC, ECHO, DF, BS = 510303, 510304, 510301, 510302
CONFIDENT, OVERLOADED = 510307, 510342


@pytest.fixture(scope="module")
def amber(gd):
    return load_team(gd, TEAMS / "amber_laru_flora.yaml")


@pytest.fixture
def one_damage_per_hit(monkeypatch):
    """Every hit deals 1 damage, so an action's damage counts its hits."""
    monkeypatch.setattr(sim_module, "hit_damage", lambda *a, **kw: 1.0)


def _shot_time(gd, team, build, k, extra=None):
    """When the k-th auto shot of the fight lands: the shortest fight (in ticks) that holds k shots."""
    lo, hi = 0, int(20 / team.tick)
    while lo < hi:
        mid = (lo + hi) // 2
        r = simulate(gd, replace(team, fight_length=mid * team.tick), build, extra=extra)
        if r.by_slot.get((0, "auto"), 0) >= k:
            hi = mid
        else:
            lo = mid + 1
    return lo * team.tick


def test_confident_mode_matches_the_frame_timing(gd, amber, one_damage_per_hit):
    # User (30 fps): 12 shots take 2.00 s at base (the kit's own timing is 2.03 s), 43 frames after the skill.
    t = with_pinks(amber, 0, [DF, BS])
    magazine = lambda b: _shot_time(gd, t, b, 12) - _shot_time(gd, t, b, 1)
    assert magazine(Build()) == pytest.approx(2.03, abs=0.05)
    assert magazine(Build().with_potential(AMBER, CONFIDENT, 1)) == pytest.approx(43 / 30, abs=0.05)


def test_always_on_atk_spd_scales_the_whole_string(gd, amber, one_damage_per_hit):
    # Shot 13 opens the second magazine: 12 shots and a reload, 2.80 s at base. +100% halves all of it.
    t = with_pinks(amber, 0, [BS, ECHO])
    period = lambda spd: (_shot_time(gd, t, Build(), 13, [(0, Modifier(stat=ATK_SPD, value=spd, source="t"))])
                          - _shot_time(gd, t, Build(), 1, [(0, Modifier(stat=ATK_SPD, value=spd, source="t"))]))
    assert period(0.0) == pytest.approx(2.80, abs=0.05)
    assert period(1.0) == pytest.approx(1.40, abs=0.05)


def test_atk_spd_on_a_support_does_not_speed_up_the_main(gd, amber):
    base = simulate(gd, amber, Build()).total
    assert simulate(gd, amber, Build(), extra=[(1, Modifier(stat=ATK_SPD, value=1.0, source="t"))]).total == base


def test_support_potential_can_speed_up_the_main(gd):
    # Teresa's Isn't It Awesome!: ATK SPD for the main while Surging Shield is up.
    t = load_team(gd, TEAMS / "chitose_freesia_teresa.yaml")
    without = simulate(gd, t, Build())
    with_it = simulate(gd, t, Build().with_potential(127, 512725, 1))
    assert with_it.by_slot[(0, "auto")] > without.by_slot[(0, "auto")]


def _ult_team(amber):
    return replace(with_pinks(amber, 0, [PTC, BS]), fight_length=600.0)


def _casts_after_ult(gd, team, build, extra, seconds):
    """Skill casts from the first ult up to `seconds` after it."""
    u = simulate(gd, team, build, extra=extra).first_cast[(0, "ult")]
    casts = lambda T: simulate(gd, replace(team, fight_length=T), build, extra=extra).casts[(0, "skill")]
    return casts(u + seconds) - casts(u)


def test_overloaded_spark_halves_the_cd_right_after_the_ult(gd, amber):
    # Ult (lock 1.167), skill and recast: the CD starts at the recast's dodge, 3.566 s after the skill.
    # With a 4 s CD the next skill comes at +8.733; with 8 s at +12.733.
    t = _ult_team(amber)
    build = Build().with_potential(AMBER, OVERLOADED, 1)
    assert _casts_after_ult(gd, t, build, None, 8.9) == 2
    reset_only = ResolvedPotential(potential_id=-1, level=1, modifiers=[], notes=[], add_hits={}, replace_hits={},
                                   add_actions={}, mark_tags=(), extra_casts={}, reset_cd={"ult": "skill"},
                                   cd_reduce=None, procs=[])
    assert _casts_after_ult(gd, t, Build(), [(0, reset_only)], 8.9) == 1


def test_overloaded_spark_window_closes(gd, amber):
    # The 2nd skill's CD starts at +12.3, after the window (+9.167): the full 8 s, so the 3rd skill comes at +20.3.
    t = _ult_team(amber)
    build = Build().with_potential(AMBER, OVERLOADED, 1)
    assert _casts_after_ult(gd, t, build, None, 20.1) == 2
    assert _casts_after_ult(gd, t, build, None, 20.5) == 3


def _cast_times(monkeypatch, gd, team, build):
    """{action: [cast times]} of the main, read off the hits each cast queues (first hit of each cast; only differences matter)."""
    pushed = {}
    real = sim_module.heapq.heappush

    class Recorder:
        heappop = staticmethod(sim_module.heapq.heappop)

        @staticmethod
        def heappush(queue, item):
            t, _, member, _, action, cid = item
            if member == 0 and action in ("skill", "ult"):
                pushed.setdefault(cid, t)
            real(queue, item)

    monkeypatch.setattr(sim_module, "heapq", Recorder)
    r = simulate(gd, team, build)
    monkeypatch.undo()
    times = {"skill": [], "ult": []}
    for cid, t in pushed.items():
        times[cid.split("#")[0]].append(t)
    return r, {k: sorted(v) for k, v in times.items()}


@pytest.mark.parametrize("name", ["amber_laru_flora", "amber_flora_chixia", "amber_chixia_laru"])
def test_overloaded_spark_halves_one_cd_per_ult_with_the_recast(monkeypatch, gd, name):
    # User: with the recast, only one cooldown is halved per ult. Skill to skill: 3.566 s + the CD, 7.566 s halved, 11.566 s full.
    team = replace(load_team(gd, TEAMS / f"{name}.yaml"), fight_length=600.0)
    _, times = _cast_times(monkeypatch, gd, team, Build().with_potential(AMBER, OVERLOADED, 1))
    assert len(times["ult"]) >= 10
    for u, next_u in zip(times["ult"], times["ult"][1:]):
        after = [s for s in times["skill"] if u < s < next_u]
        assert len(after) >= 3
        assert after[1] - after[0] == pytest.approx(7.566, abs=0.1)
        assert after[2] - after[1] == pytest.approx(11.566, abs=0.1)
