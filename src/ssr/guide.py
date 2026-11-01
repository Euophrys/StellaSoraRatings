"""Analysis behind the build guide page (`python -m ssr.web`).

Every number comes from `simulate`. Each function takes `progress(phase, done, total)`, called once per
simulate call; a progress callback may raise to cancel the run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .builds import PinkBuildRow, pink_pairs, score_pinks
from .compare import greedy_build
from .data import GameData
from .emblems import emblem_options, line_relevant
from .game import potential_pools
from .rate import gain
from .sim import simulate
from .team import Build, TeamConfig

Progress = Callable[[str, int, int], None] | None
LEVELS = range(1, 7)


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
    """(member, potential) -> 6 values: team-damage change if that potential's target were 1..6."""
    members = list(range(len(team.members))) if members is None else members
    cells = [(i, p) for i in members for p in _pool(gd, team, i)]
    total = 1 + sum(1 for i, p in cells for lv in LEVELS
                    if lv != build.potentials.get((team.members[i].char_id, p), 0))
    step = _tick(progress, "potentials", total)
    base = simulate(gd, team, build)
    step()
    out = {}
    for i, p in cells:
        cid = team.members[i].char_id
        cur = build.potentials.get((cid, p), 0)
        row = []
        for lv in LEVELS:
            if lv == cur:
                row.append(0.0)
                continue
            row.append(gain(base, simulate(gd, team, _set_level(build, cid, p, lv))))
            step()
        out[(i, p)] = row
    return out


# ---------------------------------------------------------------- emblem lines

@dataclass
class EmblemRow:
    name: str
    kind: str
    slots: list[int]
    relevant: bool
    tiers: list[tuple[str, str, float]]   # (label, colour, team gain)


def emblem_table(gd: GameData, team: TeamConfig, build: Build, member: int,
                 progress: Progress = None) -> list[EmblemRow]:
    """Every line this member can roll, each tier's team-damage gain on top of the build + owned emblems."""
    m = team.members[member]
    element = gd.table("Character")[str(m.char_id)]["EET"]
    opts = emblem_options(gd, m.char_id)
    relevant = {o.name: line_relevant(o.tiers[0].line, element, m.role) for o in opts}
    step = _tick(progress, "emblems", 1 + sum(len(o.tiers) for o in opts if relevant[o.name]))
    base = simulate(gd, team, build)
    step()
    rows = []
    for o in opts:
        tiers = []
        for t in o.tiers:
            g = 0.0
            if relevant[o.name]:
                g = gain(base, simulate(gd, team, build, extra=[(member, t.line)]))
                step()
            tiers.append((t.label, t.colour, g))
        rows.append(EmblemRow(o.name, o.kind, sorted(o.slots), relevant[o.name], tiers))
    rows.sort(key=lambda r: (-r.tiers[-1][2], not r.relevant))
    return rows


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
             progress: Progress = None, max_passes: int = 5) -> OptimizeResult:
    """Greedy +1 steps within each member's budget, then swap polish: move one level between two potentials
    of the same member while that raises team damage (the budget split stays satisfied)."""
    steps = sum(split)
    done = [0]

    def greedy_progress(_msg):
        done[0] += 1
        if progress:
            progress("optimize: greedy", done[0], steps)
    g = greedy_build(gd, team, max_level=max_level, split=split, progress=greedy_progress)
    build = g.build
    best_total = g.totals[-1] if g.totals else g.base_total
    swaps = 0
    pools = [_pool(gd, team, i) for i in range(len(team.members))]
    for pass_no in range(max_passes):
        moves = []
        for i, m in enumerate(team.members):
            cid = m.char_id
            for a in pools[i]:
                la = build.potentials.get((cid, a), 0)
                if la < 1:
                    continue
                for b in pools[i]:
                    lb = build.potentials.get((cid, b), 0)
                    if b != a and lb < max_level:
                        moves.append((cid, a, la, b, lb))
        best_move = None
        for k, (cid, a, la, b, lb) in enumerate(moves):
            cand = _set_level(_set_level(build, cid, a, la - 1), cid, b, lb + 1)
            tot = simulate(gd, team, cand).total
            if progress:
                progress(f"optimize: swap pass {pass_no + 1}", k + 1, len(moves))
            if tot > best_total * (1 + 1e-12):
                best_total, best_move = tot, cand
        if best_move is None:
            break
        build = best_move
        swaps += 1
    method = f"greedy + {swaps} swap{'s' if swaps != 1 else ''}"
    return OptimizeResult(build, best_total, g.base_total, method)
