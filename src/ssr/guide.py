"""Analysis behind the build guide page (`python -m ssr.web`).

Every number comes from `simulate`. Each function takes `progress(phase, done, total)`, called once per
simulate call; a progress callback may raise to cancel the run.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from .builds import PinkBuildRow, pink_pairs, score_pinks
from .compare import greedy_build
from .data import GameData
from .emblems import emblem_options, line_relevant
from .game import potential_pools
from .parallel import simulate_many
from .rate import gain, rate_discs
from .stats import ELEMENTS
from .team import Build, TeamConfig

Progress = Callable[[str, int, int], None] | None
LEVELS = range(1, 7)


def without_breaks(team: TeamConfig) -> TeamConfig:
    """The team in a fight with no breaks. Any damage gain moves the break windows, which can make plain ATK look
    negative against the burst timings, so the page's numbers leave them out unless asked."""
    return replace(team, enemy=replace(team.enemy, breaks=False))


def _tick(progress: Progress, phase: str, total: int):
    done = [0]

    def step():
        done[0] += 1
        if progress:
            progress(phase, done[0], total)
    return step


def _set_level(build: Build, cid: int, pid: int, lv: int) -> Build:
    return build.with_potential(cid, pid, lv) if lv > 0 else build.without(cid, pid)


def _pool(gd: GameData, team: TeamConfig, i: int) -> list[int]:
    m = team.members[i]
    pools = potential_pools(gd, m.char_id, m.role)
    return pools["normal"] + pools["common"]


# ---------------------------------------------------------------- potential grid

def potential_grid(gd: GameData, team: TeamConfig, build: Build, members: list[int] | None = None,
                   progress: Progress = None) -> dict[tuple[int, int], list[float]]:
    """(member, potential) -> 6 values: team-damage change if that potential's target were 1..6.

    The current level's cell is instead the change from removing the potential entirely, so the value of what's
    already taken shows too."""
    members = list(range(len(team.members))) if members is None else members
    cells = [(i, p) for i in members for p in _pool(gd, team, i)]
    total = 1 + len(cells) * len(LEVELS)
    step = _tick(progress, "potentials", total)
    calls = [dict(build=build)]
    for i, p in cells:
        cid = team.members[i].char_id
        cur = build.potentials.get((cid, p), 0)
        calls += [dict(build=_set_level(build, cid, p, 0 if lv == cur else lv)) for lv in LEVELS]
    results = simulate_many(gd, team, calls, step)
    base, rest = results[0], iter(results[1:])
    return {cell: [gain(base, next(rest)) for _ in LEVELS] for cell in cells}


# ---------------------------------------------------------------- emblem lines

@dataclass
class EmblemRow:
    name: str
    kind: str
    slots: list[int]
    relevant: bool
    tiers: list[tuple[str, str, float]]   # (label, colour, team gain) in the line's first slot
    by_slot: dict[int, list[float]]       # slot -> team gain per tier; see emblem_table


def emblem_table(gd: GameData, team: TeamConfig, build: Build, member: int,
                 progress: Progress = None) -> list[EmblemRow]:
    """Every line this member can roll, each tier's team-damage gain on top of the build + owned emblems.

    A line that rolls in several slots (stat lines: Lv70, Lv80, Lv90) is valued as the n-th copy in slot n:
    slot 2 is the gain of a second line on top of the same line (same tier) on emblem 1, slot 3 the third."""
    m = team.members[member]
    element = gd.table("Character")[str(m.char_id)]["EET"]
    opts = emblem_options(gd, m.char_id)
    relevant = {o.name: line_relevant(o.tiers[0].line, element, m.role) for o in opts}
    step = _tick(progress, "emblems", 1 + sum(len(o.tiers) * len(o.slots) for o in opts if relevant[o.name]))
    calls = [dict(build=build)]
    for o in opts:
        if relevant[o.name]:
            calls += [dict(build=build, extra=[(member, t.line)] * n) for t in o.tiers for n in range(1, len(o.slots) + 1)]
    results = simulate_many(gd, team, calls, step)
    base, rest = results[0], iter(results[1:])
    rows = []
    for o in opts:
        slots = sorted(o.slots)
        by_slot: dict[int, list[float]] = {s: [] for s in slots}
        for t in o.tiers:
            prev = base
            for s in slots:
                g = 0.0
                if relevant[o.name]:
                    r = next(rest)
                    g, prev = gain(prev, r), r
                by_slot[s].append(g)
        tiers = [(t.label, t.colour, by_slot[slots[0]][k]) for k, t in enumerate(o.tiers)]
        rows.append(EmblemRow(o.name, o.kind, slots, relevant[o.name], tiers, by_slot))
    rows.sort(key=lambda r: (-r.tiers[-1][2], not r.relevant))
    return rows


# ---------------------------------------------------------------- discs

def disc_table(gd: GameData, team: TeamConfig, build: Build, progress: Progress = None) -> list[dict]:
    """Every available disc, each alone at C1 and C6 in one main or support slot (the other five slots filler), as
    the team-damage gain over six fillers, on the current build and owned emblems. `on_element` marks discs of a
    team member's element. Starts with the filler itself (0 by definition), then by best main-slot C6 gain."""
    elements = {gd.table("Character")[str(m.char_id)].get("EET", 0) for m in team.members}
    ids = sorted(int(k) for k, v in gd.table("Disc").items() if v.get("Available") and v.get("Visible"))
    step = _tick(progress, "discs", 1 + 4 * len(ids))
    rows = rate_discs(gd, team, ids, build=build, emblems=True, on_result=step)
    rows.sort(key=lambda r: (-r.main_c6, -r.main_c1))
    disc = gd.table("Disc")
    out = [dict(id=0, name="filler", element="", on_element=True, main_c1=0.0, main_c6=0.0, support_c1=0.0, support_c6=0.0,
                notes=["stats only, no effects: the baseline"])]
    out += [dict(id=r.disc_id, name=r.name, element=ELEMENTS.get(disc[str(r.disc_id)].get("EET", 0), "Neutral"),
                 on_element=disc[str(r.disc_id)].get("EET", 0) in elements,
                 main_c1=r.main_c1, main_c6=r.main_c6, support_c1=r.support_c1, support_c6=r.support_c6,
                 notes=r.notes) for r in rows]
    return out


# ---------------------------------------------------------------- pinks

def rank_pinks(gd: GameData, team: TeamConfig, member: int, progress: Progress = None) -> list[PinkBuildRow]:
    """Every pink pair for a member, scored on the reference build with the team's own discs."""
    pairs = pink_pairs(gd, team, member)
    rows = []
    for k, pair in enumerate(pairs):
        if progress:
            progress("pinks", k, len(pairs))
        rows.append(score_pinks(gd, team, member, pair, own_discs=False))
    if progress:
        progress("pinks", len(pairs), len(pairs))
    rows.sort(key=lambda r: -r.total_team_discs)
    return rows


# ---------------------------------------------------------------- optimize

@dataclass
class OptimizeResult:
    build: Build
    total: float
    base_total: float
    method: str


def optimize(gd: GameData, team: TeamConfig, split: list[int], max_level: int = 6,
             progress: Progress = None, max_passes: int = 5, total: int | None = None) -> OptimizeResult:
    """Greedy +1 steps within each member's budget, then swap polish: move one level between two potentials
    while that raises team damage. With `total`, `split` holds per-member caps on a shared budget, and levels may
    also move between members (within the caps); otherwise only within a member (the split stays satisfied)."""
    steps = min(total, sum(split)) if total is not None else sum(split)
    done = [0]

    def greedy_progress(_msg):
        done[0] += 1
        if progress:
            progress("optimize: greedy", done[0], steps)
    g = greedy_build(gd, team, max_level=max_level, split=split, progress=greedy_progress, total=total)
    build = g.build
    best_total = g.totals[-1] if g.totals else g.base_total
    swaps = 0
    pools = [_pool(gd, team, i) for i in range(len(team.members))]
    for pass_no in range(max_passes):
        moves = []
        used = [sum(build.potentials.get((m.char_id, p), 0) for p in pools[i]) for i, m in enumerate(team.members)]
        for i, m in enumerate(team.members):
            cid = m.char_id
            for a in pools[i]:
                la = build.potentials.get((cid, a), 0)
                if la < 1:
                    continue
                for j, mj in enumerate(team.members):
                    if j != i and (total is None or used[j] >= split[j]):
                        continue   # across members only on a shared budget, within the receiver's cap
                    for b in pools[j]:
                        lb = build.potentials.get((mj.char_id, b), 0)
                        if (j, b) != (i, a) and lb < max_level:
                            moves.append((cid, a, la, mj.char_id, b, lb))
        best_move = None
        cands = [_set_level(_set_level(build, cid, a, la - 1), cidb, b, lb + 1) for cid, a, la, cidb, b, lb in moves]
        step = _tick(progress, f"optimize: swap pass {pass_no + 1}", len(moves))
        results = simulate_many(gd, team, [dict(build=c) for c in cands], step)
        for cand, r in zip(cands, results):   # in move order: among equal totals the first one wins
            if r.total > best_total * (1 + 1e-12):
                best_total, best_move = r.total, cand
        if best_move is None:
            break
        build = best_move
        swaps += 1
    method = f"greedy + {swaps} swap{'s' if swaps != 1 else ''}"
    return OptimizeResult(build, best_total, g.base_total, method)
