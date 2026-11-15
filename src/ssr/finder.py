"""Team finder: the best teams for one Trekker, each at its own best build.

A build is made during a run with all three Trekkers, so "who should I pair with X?" compares teams each at its own
best build: pinks, potentials and emblems re-chosen per team. From a template team document (discs, enemy, fight,
budget), every same-element team that has the Trekker in the chosen role is generated, then per team:

1. pinks: member by member, each pair scored on the team's reference build with the template's discs;
2. screen: a coarse greedy where each step takes one potential straight to Lv6 (5 picks on the main, 3 per support);
3. finalists (top N by screen): the build guide's optimize, then greedy emblems.

Design: docs/superpowers/specs/2026-11-13-team-finder-design.md.
"""
from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import yaml

from .builds import search_pinks
from .compare import COLOUR_RANK, greedy_emblems
from .data import DEFAULT_DATA_ROOT, REPO_ROOT, GameData
from .finder_page import render_html
from .game import char_element, levelled_potentials
from .guide import _pool, optimize, without_breaks
from .kit import SPECS, role_status
from .parallel import simulate_many
from .team import Build, TeamConfig, team_from_doc

ROLES = ("main", "support", "any")


def _has_kit(cid: int, role: str) -> bool:
    return role_status(SPECS / f"{cid}.yaml", role) not in ("missing", "stub")


def _candidates(gd: GameData, element: int) -> list[int]:
    from .web.catalog import trekker_ids
    chars = gd.table("Character")
    return [c for c in trekker_ids() if str(c) in chars and char_element(gd, c) == element]


def _member(gd: GameData, cid: int, role: str) -> dict:
    return {"trekker": gd.char_name(cid), "role": role, "pinks": [], "skill_levels": {}, "emblems": [], "targets": {}}


def _doc(gd: GameData, template: dict, main: int, supports: tuple[int, int]) -> dict:
    doc = copy.deepcopy(template)
    doc.pop("hold", None)   # names members by index: meaningless for other members
    doc["members"] = [_member(gd, main, "main")] + [_member(gd, s, "support") for s in supports]
    doc["name"] = "_".join(gd.char_name(c) for c in (main, *supports)).lower().replace(" ", "_")
    ref = doc.get("reference")
    if isinstance(ref, dict) and ref.get("include"):
        have = set()
        for cid, role in [(main, "main")] + [(s, "support") for s in supports]:
            have |= {gd.item_name(p) for p in levelled_potentials(gd, cid, role)}
        ref["include"] = [n for n in ref["include"] if n in have]
    return doc


def find_trekker(gd: GameData, name: str) -> int:
    """Char id by name, ignoring case and surrounding spaces."""
    want = str(name).strip().casefold()
    hits = [int(k) for k in gd.table("Character") if gd.char_name(int(k)).casefold() == want]
    if len(hits) != 1:
        raise ValueError(f"unknown trekker {name!r}" if not hits else f"trekker {name!r} is ambiguous")
    return hits[0]


def team_docs(gd: GameData, template: dict, trekker: str, role: str = "main", exclude=()) -> list[dict]:
    """One team document per candidate team: `trekker` in `role` ("main", "support" or "any") with every pair of
    same-element Trekkers that have a kit for the slot they'd fill. Main first; supports ordered by char id."""
    role = str(role).strip().lower()
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}, not {role!r}")
    cid = find_trekker(gd, trekker)
    roles = ("main", "support") if role == "any" else (role,)
    if not any(_has_kit(cid, r) for r in roles):
        raise ValueError(f"{gd.char_name(cid)} has no {role} kit")
    skip = {find_trekker(gd, n) for n in exclude}
    others = [c for c in _candidates(gd, char_element(gd, cid)) if c != cid and c not in skip]
    teams: list[tuple[int, tuple[int, int]]] = []
    if "main" in roles and _has_kit(cid, "main"):
        sup = [c for c in others if _has_kit(c, "support")]
        teams += [(cid, pair) for pair in combinations(sup, 2)]
    if "support" in roles and _has_kit(cid, "support"):
        for main in others:
            if not _has_kit(main, "main"):
                continue
            sup = [c for c in others if c != main and _has_kit(c, "support")]
            teams += [(main, tuple(sorted((cid, s)))) for s in sup]
    teams.sort(key=lambda t: (t[0], t[1]))
    return [_doc(gd, template, main, sup) for main, sup in teams]


def coarse_build(gd: GameData, team: TeamConfig, picks: tuple[int, int, int] = (5, 3, 3), level: int = 6,
                 progress=None) -> tuple[Build, float]:
    """The screen: each step adds the one potential at `level` (any member with picks left) that raises team damage
    the most, until every member has used its `picks` or nothing helps. Returns (build, its total)."""
    build = Build()
    pools = [_pool(gd, team, i) for i in range(len(team.members))]
    left = list(picks)
    steps = sum(picks)
    cur = simulate_many(gd, team, [dict(build=build)])[0].total
    for step in range(steps):
        cands = [(i, p) for i, m in enumerate(team.members) if left[i] > 0
                 for p in pools[i] if (m.char_id, p) not in build.potentials]
        if not cands:
            break
        builds = [build.with_potential(team.members[i].char_id, p, level) for i, p in cands]
        results = simulate_many(gd, team, [dict(build=b) for b in builds])
        best = max(range(len(cands)), key=lambda k: results[k].total)   # first of equal totals wins
        if results[best].total <= cur * (1 + 1e-12):
            break
        build, cur = builds[best], results[best].total
        left[cands[best][0]] -= 1
        if progress:
            progress("screen", step + 1, steps)
    return build, cur


@dataclass
class FinderRow:
    members: list[str]                 # trekker names, main first
    pinks: list[list[str]]             # per member, 2 names
    screen_total: float | None
    total: float | None = None         # finalists only: after optimize (+ emblems)
    finalist: bool = False
    method: str = ""                   # optimize's method string, finalists only
    doc: dict | None = None            # pinks + targets (screen build, or optimized for finalists) + emblems (finalists)
    error: str | None = None


def _err(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _fill_doc(gd: GameData, doc: dict, team: TeamConfig, build: Build, emblem_slots: dict | None = None) -> dict:
    doc = copy.deepcopy(doc)
    for i, (m, md) in enumerate(zip(team.members, doc["members"])):
        md["pinks"] = [gd.item_name(p) for p in m.pinks]
        md["targets"] = {gd.item_name(p): lv for p, lv in sorted(build.levels_for(m.char_id).items())}
        md["emblems"] = [{"slot": s, "lines": [{"line": n, "tier": t} for n, t in lines]}
                         for s, lines in sorted((emblem_slots or {}).get(i, {}).items()) if lines]
    return doc


def find_teams(gd: GameData, template: dict, trekker: str, role: str = "main", top: int = 5,
               emblems: str = "purple", picks=(5, 3, 3), breaks: bool = False, exclude=(),
               progress=None) -> list[FinderRow]:
    """Every team with `trekker` in `role` (see team_docs), ranked. Each gets its own pinks (searched on its
    reference build with the template's discs) and a screen build (coarse_build); the top `top` by screen are
    optimized with the template's budget, then get greedy emblems at tier `emblems` ("none" skips them).
    Rows: finalists by total, then the rest by screen total, failed teams last."""
    emblems = emblems.strip().lower()
    docs = team_docs(gd, template, trekker, role, exclude)
    rows: list[FinderRow] = []
    teams: list[TeamConfig | None] = []

    def tick(phase, done, total):
        if progress:
            progress(phase, done, total)
    for k, doc in enumerate(docs):
        names = [m["trekker"] for m in doc["members"]]
        phase = f"screen: {doc['name']}"
        tick(phase, k, len(docs))
        try:
            team = team_from_doc(gd, doc, doc["name"])
            rated = team if breaks else without_breaks(team)
            rated, _ = search_pinks(gd, rated, [0, 1, 2], own_discs=False,
                                    progress=lambda _i, _pair: tick(phase, k, len(docs)))
            build, screen = coarse_build(gd, rated, picks, progress=lambda *_: tick(phase, k, len(docs)))
        except Exception as e:   # noqa: BLE001 - one bad team is listed, not fatal (JobCancelled isn't an Exception)
            rows.append(FinderRow(names, [[] for _ in names], None, doc=doc, error=_err(e)))
            teams.append(None)
            continue
        rows.append(FinderRow(names, [[gd.item_name(p) for p in m.pinks] for m in rated.members], screen,
                              doc=_fill_doc(gd, doc, rated, build)))
        teams.append(rated)
    tick("screen", len(docs), len(docs))

    ok = sorted((k for k, r in enumerate(rows) if r.error is None), key=lambda k: -rows[k].screen_total)
    finalists = ok[:top]
    for n, k in enumerate(finalists):
        row, team = rows[k], teams[k]
        phase = f"finalist {n + 1}/{len(finalists)}: {docs[k]['name']}"
        tick(phase, n, len(finalists))
        row.finalist = True
        try:
            r = optimize(gd, team, list(team.budget), max_level=team.max_level, total=team.budget_total,
                         progress=lambda *_: tick(phase, n, len(finalists)))
            row.total, row.method, slots = r.total, r.method, None
            if emblems != "none":
                er = greedy_emblems(gd, team, r.build, tier=emblems, progress=lambda _m: tick(phase, n, len(finalists)))
                row.total, slots = (er.totals[-1] if er.totals else er.base_total), er.slots
            row.doc = _fill_doc(gd, docs[k], team, r.build, slots)
        except Exception as e:   # noqa: BLE001
            row.error = _err(e)
    tick("done", len(finalists), len(finalists))

    def key(r: FinderRow):
        if r.error is not None:
            return (2, 0.0)
        return (0, -r.total) if r.finalist else (1, -r.screen_total)
    return sorted(rows, key=key)


def _picks(s: str) -> tuple[int, int, int]:
    out = tuple(int(x) for x in s.split(","))
    if len(out) != 3 or min(out) < 0:
        raise argparse.ArgumentTypeError("picks must be 3 non-negative whole numbers, e.g. 5,3,3")
    return out


def format_rows(rows: list[FinderRow]) -> list[str]:
    """A short terminal summary: the finalists' ranking; the full tables are in the page."""
    fin = [r for r in rows if r.finalist and r.error is None]
    best = max((r.total for r in fin), default=0) or 1
    lines = ["Finalists (full build):"] + [f"  {n}. {' / '.join(r.members):<44} {100 * r.total / best:7.2f}%"
                                         for n, r in enumerate(fin, 1)]
    failed = sum(r.error is not None for r in rows)
    lines.append(f"Screened {len(rows)} teams" + (f", {failed} failed" if failed else "") + ".")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rank every same-element team for one Trekker, each at its own best build")
    ap.add_argument("trekker")
    ap.add_argument("--template", required=True, help="team file whose discs, enemy, fight and budget every team uses")
    ap.add_argument("--role", type=str.lower, choices=ROLES, default="main")
    ap.add_argument("--top", type=int, default=5, help="finalists that get the full optimize + emblems")
    ap.add_argument("--emblems", type=str.lower, choices=[*sorted(COLOUR_RANK, key=COLOUR_RANK.get), "none"], default="purple")
    ap.add_argument("--picks", type=_picks, default=(5, 3, 3), help="screen picks per member at Lv6 (main first)")
    ap.add_argument("--breaks", action="store_true", help="rate with enemy breaks (off by default, as on the page)")
    ap.add_argument("--exclude", nargs="*", default=[], metavar="TREKKER")
    ap.add_argument("-o", "--out", help="write the finalists' team documents here (a YAML list)")
    ap.add_argument("--html", help="results page (default out/finder_<trekker>_<role>.html)")
    ap.add_argument("--no-open", action="store_true", help="don't open the page in a browser")
    a = ap.parse_args(argv)
    gd = GameData(DEFAULT_DATA_ROOT)
    template = yaml.safe_load(Path(a.template).read_text(encoding="utf-8"))
    try:
        who = gd.char_name(find_trekker(gd, a.trekker))
        a.exclude = [gd.char_name(find_trekker(gd, n)) for n in a.exclude]
    except ValueError as e:
        ap.error(str(e))
    last = [None]

    def progress(phase, _done, _total):
        if phase != last[0]:
            last[0] = phase
            print(phase, file=sys.stderr, flush=True)
    rows = find_teams(gd, template, who, a.role, top=a.top, emblems=a.emblems, picks=a.picks,
                      breaks=a.breaks, exclude=a.exclude, progress=progress)
    print("\n".join(format_rows(rows)))
    page = Path(a.html or REPO_ROOT / "out" / f"finder_{who.lower().replace(' ', '_')}_{a.role}.html")
    page.parent.mkdir(parents=True, exist_ok=True)
    settings = [f"Template {a.template}; finalists {a.top}; emblems {a.emblems}; screen picks "
                f"{' / '.join(map(str, a.picks))} at Lv6; breaks {'on' if a.breaks else 'off'}"
                + (f"; excluded {', '.join(a.exclude)}" if a.exclude else "")]
    page.write_text(render_html(rows, f"Team finder: {who} as {a.role}", settings), encoding="utf-8")
    print(f"Wrote {page}")
    if not a.no_open:
        import webbrowser
        webbrowser.open(page.resolve().as_uri())
    if a.out:
        Path(a.out).write_text(yaml.safe_dump([r.doc for r in rows if r.finalist and r.error is None],
                                              sort_keys=False, allow_unicode=True), encoding="utf-8")


if __name__ == "__main__":
    main()
