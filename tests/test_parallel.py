from dataclasses import replace

import pytest

from ssr import parallel
from ssr.guide import _pool, potential_grid
from ssr.parallel import simulate_many
from ssr.sim import simulate
from ssr.team import Build


@pytest.fixture
def short_team(team):
    return replace(team, fight_length=10.0)


@pytest.fixture
def workers(monkeypatch):
    monkeypatch.setenv("SSR_WORKERS", "3")
    yield
    parallel.shutdown()


def _calls(gd, team, n=12):
    cid = team.members[0].char_id
    return [dict(build=Build().with_potential(cid, p, 1 + k % 6)) for k, p in enumerate(_pool(gd, team, 0)[:n])]


def test_workers_give_the_serial_results_in_call_order(gd, short_team, workers):
    calls = _calls(gd, short_team)
    assert len(calls) >= parallel.MIN_PARALLEL
    seen = []
    got = simulate_many(gd, short_team, calls, on_result=lambda: seen.append(1))
    assert parallel._pool is not None   # it did go through the workers
    assert got == [simulate(gd, short_team, **c) for c in calls]
    assert len(seen) == len(calls)


def test_small_batches_and_one_worker_stay_in_process(gd, short_team, workers, monkeypatch):
    calls = _calls(gd, short_team)
    simulate_many(gd, short_team, calls[:parallel.MIN_PARALLEL - 1])
    assert parallel._pool is None
    monkeypatch.setenv("SSR_WORKERS", "1")
    assert simulate_many(gd, short_team, calls) == [simulate(gd, short_team, **c) for c in calls]
    assert parallel._pool is None


def test_cancel_propagates_and_the_workers_stay_usable(gd, short_team, workers):
    class Stop(Exception):
        pass

    def boom():
        raise Stop
    calls = _calls(gd, short_team)
    with pytest.raises(Stop):
        simulate_many(gd, short_team, calls, on_result=boom)
    assert simulate_many(gd, short_team, calls) == [simulate(gd, short_team, **c) for c in calls]


def test_a_dead_worker_falls_back_to_in_process(gd, short_team, workers):
    calls = _calls(gd, short_team)
    simulate_many(gd, short_team, calls)
    for p in list(parallel._pool._processes.values()):
        p.kill()
    assert simulate_many(gd, short_team, calls) == [simulate(gd, short_team, **c) for c in calls]


def test_the_grid_is_the_same_with_workers(gd, short_team, workers, monkeypatch):
    with_workers = potential_grid(gd, short_team, Build(), members=[2])
    monkeypatch.setenv("SSR_WORKERS", "1")
    assert potential_grid(gd, short_team, Build(), members=[2]) == with_workers
