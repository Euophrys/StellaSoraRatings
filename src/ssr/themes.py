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
