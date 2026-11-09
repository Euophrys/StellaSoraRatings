"""Run batches of `simulate` calls across CPU cores.

Every consumer (ratings, optimizer, build guide) is a loop of independent simulations on one team, so the loops hand
their batch to `simulate_many`. Results come back in call order and are the same numbers a serial loop gives.

Workers are forked once per process and kept, so they share the caller's GameData and caches as they were at the
first batch. `SSR_WORKERS` sets the worker count (default: every CPU); `SSR_WORKERS=1` runs everything in-process.
"""
from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import pickle
import signal
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from typing import Callable

from .data import GameData
from .sim import SimResult, simulate
from .team import TeamConfig

MIN_PARALLEL = 8   # smaller batches run in-process: not worth the round trip
MAX_CHUNK = 4      # calls per task: small, so progress stays smooth and a cancel wastes little

_lock = threading.Lock()
_pool: ProcessPoolExecutor | None = None
_pool_key: tuple | None = None   # (gd, workers) the pool was forked for
_GD: GameData | None = None      # the workers' GameData: set before the fork, inherited by it
_IN_WORKER = False
_TEAMS: dict = {}                # worker side: digest -> TeamConfig


def worker_count() -> int:
    try:
        n = int(os.environ.get("SSR_WORKERS", "") or (os.cpu_count() or 1))
    except ValueError:
        n = 1
    return max(1, n)


def _init_worker():
    global _IN_WORKER
    _IN_WORKER = True
    signal.signal(signal.SIGINT, signal.SIG_IGN)   # Ctrl+C is the parent's to handle


def _noop():
    return None


def _run_chunk(digest: bytes, blob: bytes, calls: list[dict]) -> list[SimResult]:
    team = _TEAMS.get(digest)
    if team is None:
        if len(_TEAMS) >= 8:
            _TEAMS.clear()
        team = _TEAMS[digest] = pickle.loads(blob)
    return [simulate(_GD, team, **kw) for kw in calls]


def shutdown() -> None:
    """Stop the workers (the next batch forks new ones)."""
    global _pool, _pool_key
    with _lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
        _pool, _pool_key = None, None


def _get_pool(gd: GameData, n: int) -> ProcessPoolExecutor | None:
    global _pool, _pool_key, _GD
    if "fork" not in mp.get_all_start_methods():
        return None
    with _lock:
        if _pool is not None and (_pool_key[0] is not gd or _pool_key[1] != n):
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None
        if _pool is None:
            _GD = gd
            _pool = ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("fork"), initializer=_init_worker)
            _pool_key = (gd, n)
        return _pool


def warm(gd: GameData) -> None:
    """Fork the workers now. A server calls this before it starts threads, so the fork happens single-threaded."""
    n = worker_count()
    if n <= 1 or _IN_WORKER:
        return
    pool = _get_pool(gd, n)
    if pool is not None:
        pool.submit(_noop).result()


def simulate_many(gd: GameData, team: TeamConfig, calls: list[dict],
                  on_result: Callable[[], None] | None = None) -> list[SimResult]:
    """`simulate(gd, team, **call)` for every call, results in call order.

    `on_result()` runs in the caller's thread once per finished simulation (in completion order); if it raises,
    the rest of the batch is dropped and the exception propagates (how a job is cancelled)."""
    calls = list(calls)
    out: list = [None] * len(calls)

    def serial(todo) -> list[SimResult]:
        for i in todo:
            out[i] = simulate(gd, team, **calls[i])
            if on_result:
                on_result()
        return out

    n = worker_count()
    if _IN_WORKER or n <= 1 or len(calls) < MIN_PARALLEL:
        return serial(range(len(calls)))
    pool = _get_pool(gd, n)
    if pool is None:
        return serial(range(len(calls)))
    try:
        pickle.dumps(calls, pickle.HIGHEST_PROTOCOL)   # the calls must be able to cross too
        blob = pickle.dumps(team, pickle.HIGHEST_PROTOCOL)   # once per batch; workers keep the team by its digest
    except Exception:   # noqa: BLE001 - something unpicklable in a team or an extra: just run it here
        return serial(range(len(calls)))
    digest = hashlib.blake2b(blob, digest_size=16).digest()
    size = max(1, min(MAX_CHUNK, len(calls) // (n * 2)))
    futures = {}
    try:
        for i in range(0, len(calls), size):
            futures[pool.submit(_run_chunk, digest, blob, calls[i:i + size])] = i
        for f in as_completed(futures):
            i = futures[f]
            res = f.result()
            out[i:i + len(res)] = res
            if on_result:
                for _ in res:
                    on_result()
    except BrokenProcessPool:   # a worker died: finish in-process, fork fresh workers next time
        shutdown()
        return serial([i for i, r in enumerate(out) if r is None])
    except BaseException:
        for f in futures:
            f.cancel()
        raise
    return out
