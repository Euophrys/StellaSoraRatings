"""Emblem themes: one team at several committed builds.

The optimizer picks potentials before the emblem greedy runs, one line at a time, so a build that only pays once
you commit to it (Gerie's Mark DMG emblems + Mark potentials) never surfaces. Here each theme forces its lines into
all 3 emblems of every member that deals that kind of damage, then re-searches pinks, optimizes potentials and fills
the remaining emblem lines around them, and compares each with an unforced control.

Design: docs/superpowers/specs/2026-11-15-emblem-themes-design.md.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from .builds import search_pinks
from .compare import COLOUR_RANK, greedy_emblems
from .data import DEFAULT_DATA_ROOT, REPO_ROOT, GameData
from .emblems import emblem_options
from .finder import _err, _fill_doc
from .game import levelled_potentials, potential_pools
from .guide import optimize, without_breaks
from .sim import simulate
from .team import Build, TeamConfig, team_from_doc

THEMES: dict[str, tuple[str, ...]] = {
    "Control": (),
    "Mark": ("Mark DMG",),
    "Auto": ("Auto Attack DMG",),
    "Skill": ("Skill DMG",),
    "Ultimate": ("Ultimate DMG",),
    "Crit": ("Crit Rate", "Crit DMG"),
}
_BUCKET = {"Mark": "mark", "Auto": "auto", "Skill": "skill", "Ultimate": "ult"}   # SimResult.by_slot bucket


def eligible(gd: GameData, team: TeamConfig) -> dict[str, list[int]]:
    """Theme -> members that get its lines: those who deal that kind of damage with everything the team could have
    (all 4 pinks, every potential at Lv1, no emblems). Crit: any damage at all."""
    members = [replace(m, pinks=potential_pools(gd, m.char_id, m.role)["pink"], emblems=[]) for m in team.members]
    build = Build()
    for m in members:
        for p in levelled_potentials(gd, m.char_id, m.role):
            build = build.with_potential(m.char_id, p, 1)
    r = simulate(gd, replace(team, members=members), build)
    idx = range(len(members))
    out = {"Control": [], "Crit": [i for i in idx if r.by_member.get(i, 0) > 0]}
    out.update({k: [i for i in idx if r.by_slot.get((i, b), 0) > 0] for k, b in _BUCKET.items()})
    return {k: out[k] for k in THEMES}


def _line(gd: GameData, cid: int, name: str, tier: str):
    """The line's top roll at `tier` or a lower colour (greedy_emblems' rule)."""
    o = next(o for o in emblem_options(gd, cid) if o.name == name)
    return [t for t in o.tiers if COLOUR_RANK.get(t.colour, 0) <= COLOUR_RANK[tier]][-1].line


def themed_team(gd: GameData, team: TeamConfig, lines: tuple[str, ...], members: list[int],
                tier: str = "purple") -> TeamConfig:
    """The team with every member's emblems cleared, then `lines` in all 3 emblems of each of `members`."""
    out = []
    for i, m in enumerate(team.members):
        forced = [_line(gd, m.char_id, n, tier) for n in lines] * 3 if i in members else []
        out.append(replace(m, emblems=forced, emblem_slots=[]))
    return replace(team, members=out)


@dataclass
class ThemeRow:
    theme: str
    members: list[int]                 # who got the forced lines
    names: list[str] = field(default_factory=list)     # trekker names, main first
    total: float | None = None
    pinks: list[list[str]] = field(default_factory=list)
    doc: dict | None = None            # pinks + targets + emblems as a team document
    method: str = ""
    skipped: bool = False
    error: str | None = None


def run_themes(gd: GameData, team: TeamConfig, doc: dict, tier: str = "purple", breaks: bool = False,
               keep_pinks: bool = False, progress=None) -> list[ThemeRow]:
    """One row per theme in THEMES order: pinks (unless keep_pinks), optimize and greedy emblems, all around the
    theme's forced lines. A theme no member can use is skipped; a theme that fails carries its error."""
    tier = tier.strip().lower()
    team = team if breaks else without_breaks(team)
    who = eligible(gd, team)
    names = [gd.char_name(m.char_id) for m in team.members]
    rows = []
    for theme, lines in THEMES.items():
        members = who[theme]
        row = ThemeRow(theme, members, names)
        rows.append(row)
        if theme != "Control" and not members:
            row.skipped = True
            continue

        def tick(step, theme=theme):
            if progress:
                progress(theme, step)
        try:
            t = themed_team(gd, team, lines, members, tier)
            if not keep_pinks:
                tick("pinks")
                t, _ = search_pinks(gd, t, list(range(len(t.members))), own_discs=False)
            row.pinks = [[gd.item_name(p) for p in m.pinks] for m in t.members]
            tick("optimize")
            r = optimize(gd, t, list(t.budget), max_level=t.max_level, total=t.budget_total)
            tick("emblems")
            er = greedy_emblems(gd, t, r.build, tier, pins=[(i, n, 3) for i in members for n in lines])
            row.total = er.totals[-1] if er.totals else er.base_total
            row.method = r.method
            row.doc = _fill_doc(gd, doc, t, r.build, er.slots)
        except Exception as e:   # noqa: BLE001 - one failed theme is listed, not fatal
            row.error = _err(e)
    return rows


def format_rows(rows: list[ThemeRow]) -> list[str]:
    """Terminal summary: each theme's total vs the control."""
    control = next((r.total for r in rows if r.theme == "Control" and r.total), None)
    lines = ["Themes (vs Control):"]
    for r in rows:
        if r.skipped:
            lines.append(f"  {r.theme:<9} skipped (no member deals this damage type)")
        elif r.error is not None:
            lines.append(f"  {r.theme:<9} failed: {r.error}")
        else:
            pct = f"{100 * (r.total / control - 1):+.2f}%" if control else "n/a"
            forced = ", ".join(r.names[i] for i in r.members)
            lines.append(f"  {r.theme:<9} {pct:>9}  {r.total:,.0f}" + (f"  (forced on {forced})" if forced else ""))
    return lines


def main(argv=None):
    from .themes_page import render_html
    ap = argparse.ArgumentParser(description="One team at a control build vs builds with forced emblem themes")
    ap.add_argument("team", help="team file (members, discs, enemy, fight, budget)")
    ap.add_argument("--emblems", type=str.lower, choices=sorted(COLOUR_RANK, key=COLOUR_RANK.get), default="purple")
    ap.add_argument("--breaks", action="store_true", help="rate with enemy breaks (off by default, as in the finder)")
    ap.add_argument("--keep-pinks", action="store_true", help="keep the team file's pinks instead of searching per theme")
    ap.add_argument("-o", "--out", help="write each theme's build as a team document here (a YAML list)")
    ap.add_argument("--html", help="results page (default out/themes_<team>.html)")
    ap.add_argument("--no-open", action="store_true", help="don't open the page in a browser")
    a = ap.parse_args(argv)
    gd = GameData(DEFAULT_DATA_ROOT)
    path = Path(a.team)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    team = team_from_doc(gd, doc, path.stem)

    def progress(theme, step):
        print(f"{theme}: {step}", file=sys.stderr, flush=True)
    rows = run_themes(gd, team, doc, a.emblems, breaks=a.breaks, keep_pinks=a.keep_pinks, progress=progress)
    print("\n".join(format_rows(rows)))
    page = Path(a.html or REPO_ROOT / "out" / f"themes_{path.stem}.html")
    page.parent.mkdir(parents=True, exist_ok=True)
    settings = [f"Team {a.team}; emblems {a.emblems}; pinks {'from the file' if a.keep_pinks else 'searched per theme'}; "
                f"breaks {'on' if a.breaks else 'off'}"]
    page.write_text(render_html(rows, f"Emblem themes: {path.stem}", settings), encoding="utf-8")
    print(f"Wrote {page}")
    if not a.no_open:
        import webbrowser
        webbrowser.open(page.resolve().as_uri())
    if a.out:
        Path(a.out).write_text(yaml.safe_dump([dict(r.doc, name=f"{doc.get('name', path.stem)}_{r.theme.lower()}")
                                               for r in rows if r.doc and r.error is None],
                                              sort_keys=False, allow_unicode=True), encoding="utf-8")


if __name__ == "__main__":
    main()
