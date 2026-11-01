"""One-at-a-time background jobs with progress and cooperative cancel."""
from __future__ import annotations

import itertools
import sys
import threading
import traceback
from typing import Any, Callable


class JobBusy(RuntimeError):
    pass


class JobCancelled(Exception):
    pass


class JobRunner:
    """Runs one CPU-bound job at a time in a worker thread; `start` raises JobBusy while one runs."""

    def __init__(self, keep: int = 20):
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._ids = itertools.count(1)
        self._running: str | None = None
        self._keep = keep

    def start(self, kind: str, fn: Callable[[Callable[[str, int, int], None]], Any]) -> str:
        with self._lock:
            if self._running is not None:
                cur = self._jobs[self._running]
                raise JobBusy(f"a {cur['kind']} job is still running; wait for it or cancel it")
            jid = str(next(self._ids))
            self._jobs[jid] = {"id": jid, "kind": kind, "state": "running", "phase": "", "done": 0, "total": 0,
                               "result": None, "error": None}
            self._cancel[jid] = threading.Event()
            self._running = jid
            for old in list(self._jobs)[:-self._keep]:
                self._jobs.pop(old, None)
                self._cancel.pop(old, None)
        threading.Thread(target=self._run, args=(jid, fn), daemon=True, name=f"job-{jid}").start()
        return jid

    def _run(self, jid: str, fn):
        job, flag = self._jobs[jid], self._cancel[jid]

        def progress(phase: str, done: int, total: int):
            if flag.is_set():
                raise JobCancelled()
            job.update(phase=phase, done=done, total=total)
        final: dict = {}
        try:
            final = {"state": "done", "result": fn(progress)}
        except JobCancelled:
            final = {"state": "cancelled"}
        except Exception as e:   # noqa: BLE001 - reported to the page
            traceback.print_exc(file=sys.stderr)
            final = {"state": "error", "error": f"{type(e).__name__}: {e}"}
        finally:
            with self._lock:   # state and the free slot change together, so "not running" means startable
                job.update(final or {"state": "error", "error": "job stopped"})
                self._running = None

    def status(self, jid: str) -> dict:
        if jid not in self._jobs:
            raise KeyError(jid)
        return dict(self._jobs[jid])

    def cancel(self, jid: str) -> None:
        if jid not in self._cancel:
            raise KeyError(jid)
        self._cancel[jid].set()
