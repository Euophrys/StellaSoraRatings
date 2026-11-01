"""HTTP server and JSON API for the build guide page. Binds 127.0.0.1 only."""
from __future__ import annotations

import json
import re
import sys
import traceback
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

from ..data import GameData
from ..sharecode import SharePreset, decode_share, encode_share
from ..guide import emblem_table, optimize, potential_grid, rank_pinks
from ..sim import simulate
from ..team import TEAMS, TeamConfig, TeamDocError, save_team, team_build, team_from_doc
from .catalog import catalog
from .jobs import JobBusy, JobRunner

TEAMS_DIR: Path = TEAMS
STATIC = Path(__file__).parent / "static"
STEM = re.compile(r"^[A-Za-z0-9_-]+$")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _team(gd: GameData, doc, need_pinks: bool = True, skip_pinks: int | None = None) -> TeamConfig:
    if not isinstance(doc, dict):
        raise ApiError(400, "state must be a team document")
    if len(doc.get("members") or []) != 3:
        raise ApiError(400, "pick 3 trekkers (main + 2 supports)")
    try:
        team = team_from_doc(gd, doc, doc.get("name") or "team")
    except TeamDocError as e:
        raise ApiError(400, str(e)) from e
    if need_pinks:
        for i, m in enumerate(team.members):
            if i != skip_pinks and len(m.pinks) != 2:
                raise ApiError(400, f"pick 2 pinks for {gd.char_name(m.char_id)}")
    return team


def _name_targets(gd: GameData, team: TeamConfig, build) -> list[dict[str, int]]:
    return [{gd.item_name(p): lv for p, lv in sorted(build.levels_for(m.char_id).items())} for m in team.members]


def _recalc(gd: GameData, team: TeamConfig):
    build = team_build(team)

    def run(progress):
        grid = potential_grid(gd, team, build, progress=progress)
        emblems = {}
        for i in range(len(team.members)):
            def p(phase, done, total, i=i):
                progress(f"emblems: {gd.char_name(team.members[i].char_id)}", done, total)
            emblems[str(i)] = [asdict(r) for r in emblem_table(gd, team, build, i, progress=p)]
        total = simulate(gd, team, build).total
        return {"grid": {f"{i}:{pid}": v for (i, pid), v in grid.items()}, "emblems": emblems, "total": total}
    return run


def _optimize(gd: GameData, team: TeamConfig, split, max_level):
    def run(progress):
        r = optimize(gd, team, split, max_level=max_level, progress=progress)
        return {"targets": _name_targets(gd, team, r.build), "total": r.total, "base_total": r.base_total,
                "method": r.method}
    return run


def _pinks(gd: GameData, team: TeamConfig, member: int):
    def run(progress):
        rows = rank_pinks(gd, team, member, progress=progress)
        best = rows[0].total_team_discs if rows else 0.0
        return [{"pinks": list(r.names), "total": r.total_team_discs,
                 "vs_best": (r.total_team_discs / best - 1.0) if best else 0.0} for r in rows]
    return run


class App:
    def __init__(self, gd: GameData):
        self.gd = gd
        self.jobs = JobRunner()
        self._catalog = None

    def catalog(self):
        if self._catalog is None:
            self._catalog = catalog(self.gd)
        return self._catalog

    def start_job(self, body: dict) -> dict:
        kind = body.get("kind")
        gd = self.gd
        if kind == "recalc":
            fn = _recalc(gd, _team(gd, body.get("state")))
        elif kind == "optimize":
            team = _team(gd, body.get("state"))
            split = body.get("split") or team.budget
            if (not isinstance(split, list) or len(split) != 3
                    or not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in split)):
                raise ApiError(400, "split must be 3 non-negative whole numbers")
            max_level = body.get("max_level", team.max_level)
            if not isinstance(max_level, int) or not 1 <= max_level <= 6:
                raise ApiError(400, "max_level must be 1-6")
            fn = _optimize(gd, team, split, max_level)
        elif kind == "pinks":
            member = body.get("member")
            if member not in (0, 1, 2):
                raise ApiError(400, "member must be 0, 1 or 2")
            fn = _pinks(gd, _team(gd, body.get("state"), skip_pinks=member), member)
        else:
            raise ApiError(400, f"unknown job kind {kind!r}")
        try:
            return {"id": self.jobs.start(kind, fn)}
        except JobBusy as e:
            raise ApiError(409, str(e)) from e


def _team_path(stem: str) -> Path:
    if not STEM.match(stem):
        raise ApiError(400, f"bad team name {stem!r}: use letters, digits, _ and -")
    return TEAMS_DIR / f"{stem}.yaml"


class Handler(BaseHTTPRequestHandler):
    app: App = None   # set by make_server
    server_version = "ssr-web"

    def log_message(self, fmt, *args):   # quiet: only errors go to stderr
        pass

    # ---- plumbing
    def _send(self, status: int, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, json.dumps(obj).encode(), "application/json")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError as e:
            raise ApiError(400, f"bad JSON: {e}") from e
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        return body

    def _dispatch(self, method: str):
        try:
            path = urlparse(self.path).path
            parts = [unquote(p) for p in path.strip("/").split("/")] if path.strip("/") else []
            self._route(method, path, parts)
        except ApiError as e:
            self._json(e.status, {"error": str(e)})
        except Exception as e:   # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    # ---- routes
    def _route(self, method: str, path: str, parts: list[str]):
        app = self.app
        if method == "GET" and (not parts or parts == ["index.html"]):
            return self._static("index.html")
        if method == "GET" and parts[0] == "static" and len(parts) == 2:
            return self._static(parts[1])
        if parts[:1] != ["api"]:
            raise ApiError(404, f"no route {path}")
        rest = parts[1:]
        if method == "GET" and rest == ["catalog"]:
            return self._json(200, app.catalog())
        if rest[:1] == ["teams"]:
            if method == "GET" and len(rest) == 1:
                return self._json(200, sorted(p.stem for p in TEAMS_DIR.glob("*.yaml")))
            if len(rest) == 2:
                p = _team_path(rest[1])
                if method == "GET":
                    if not p.exists():
                        raise ApiError(404, f"no team {rest[1]!r}")
                    return self._json(200, yaml.safe_load(p.read_text(encoding="utf-8")))
                if method == "PUT":
                    doc = self._body().get("state")
                    _team(app.gd, doc, need_pinks=False)
                    save_team(doc, p)
                    return self._json(200, {"saved": rest[1]})
        if rest[:1] == ["jobs"]:
            if method == "POST" and len(rest) == 1:
                return self._json(200, app.start_job(self._body()))
            try:
                if method == "GET" and len(rest) == 2:
                    return self._json(200, app.jobs.status(rest[1]))
                if method == "POST" and len(rest) == 3 and rest[2] == "cancel":
                    app.jobs.cancel(rest[1])
                    return self._json(200, {})
            except KeyError:
                raise ApiError(404, f"no job {rest[1]!r}") from None
        if rest[:1] == ["sharecode"] and method == "POST" and len(rest) == 2:
            return self._sharecode(rest[1], self._body())
        raise ApiError(404, f"no route {method} {path}")

    def _sharecode(self, action: str, body: dict):
        gd = self.app.gd
        if action == "decode":
            code = body.get("code")
            if not isinstance(code, str):
                raise ApiError(400, "code must be a string")
            try:
                p = decode_share(gd, code)
            except ValueError as e:
                raise ApiError(400, str(e)) from e
            return self._json(200, {"members": [
                {"trekker": gd.char_name(cid), "pinks": [gd.item_name(x) for x in pinks],
                 "targets": {gd.item_name(pid): lv for pid, lv in levels.items()}}
                for cid, pinks, levels in zip(p.char_ids, p.pinks, p.levels)]})
        if action == "encode":
            team = _team(gd, body.get("state"), need_pinks=False)
            preset = SharePreset([m.char_id for m in team.members], [list(m.pinks) for m in team.members],
                                 [dict(m.targets) for m in team.members])
            return self._json(200, {"code": encode_share(gd, preset)})
        raise ApiError(404, f"no route sharecode/{action}")

    def _static(self, name: str):
        f = (STATIC / name).resolve()
        if f.parent != STATIC.resolve() or not f.is_file():
            raise ApiError(404, f"no file {name}")
        self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))


def make_server(gd: GameData, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": App(gd)})
    srv = ThreadingHTTPServer((host, port), handler)
    srv.daemon_threads = True
    return srv
