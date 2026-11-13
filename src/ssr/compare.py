"""Cross-team comparison: give each team the same budget of potential levels and compare total damage.

Damage shares only say how a team's damage splits; totals are comparable across teams because every team runs
through the same simulator (enemy, fight length, skill levels, stat model). Each team gets its pinks for free,
then a greedy build: every step adds +1 level to whichever normal/common potential (any member) raises team
damage the most, up to `max_level` per potential. Each step also tries jumping a potential straight to its cap and
takes the jump if it gains more per level spent (values that come in steps, e.g. Observer Array's turret limit).

    python -m ssr.compare teams/a.yaml teams/b.yaml --budget 60 --max-level 6
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field

from .data import GameData
from .game import potential_pools
from .parallel import simulate_many
from .sim import simulate
from .team import Build, TeamConfig, load_team


@dataclass
class GreedyResult:
    team: str
    base_total: float                      # pinks only
    totals: list[float] = field(default_factory=list)   # total after each step
    picks: list[tuple[str, str, int]] = field(default_factory=list)   # (member, potential, new level)
    build: Build = field(default_factory=Build)


def greedy_build(gd: GameData, team: TeamConfig, budget: int = 60, max_level: int = 6,
                 progress=None, split: list[int] | None = None, total: int | None = None) -> GreedyResult:
    """split: per-member level caps in team order (e.g. [30, 15, 15]). The budget is their sum, or `total` when given
    (a shared pool the members draw from up to their caps, e.g. total 60 with caps 30/20/20)."""
    cands = []
    owner = {}
    for i, m in enumerate(team.members):
        pools = potential_pools(gd, m.char_id, m.role)
        for p in pools["normal"] + pools["common"]:
            cands.append((m.char_id, p))
            owner[(m.char_id, p)] = i
    if split:
        budget = min(total, sum(split)) if total is not None else sum(split)
    used = [0] * len(team.members)
    build = Build()
    cur = simulate(gd, team, build).total
    res = GreedyResult(team.name, cur, build=build)
    step = 0
    while step < budget:
        todo = []   # (cid, p, new level, levels spent)
        for cid, p in cands:
            lv = build.potentials.get((cid, p), 0)
            room = min(max_level - lv, budget - step)
            if split:
                room = min(room, split[owner[(cid, p)]] - used[owner[(cid, p)]])
            if room <= 0:
                continue
            todo.append((cid, p, lv + 1, 1))
            if room > 1:   # lookahead: a potential whose value comes in steps (Observer Array: 1/2/3 turrets at Lv1/4/6)
                todo.append((cid, p, lv + room, room))
        results = simulate_many(gd, team, [dict(build=build.with_potential(cid, p, lv)) for cid, p, lv, _ in todo])
        best = None
        for (cid, p, lv, k), r in zip(todo, results):   # in candidate order: the first of equal rates wins
            rate = (r.total - cur) / k   # gain per level spent; a jump only wins if it beats every single level
            if best is None or rate > best[0] + 1e-9 * abs(cur):
                best = (rate, r.total, cid, p, lv, k)
        if best is None:
            break
        _, new, cid, p, lv, k = best
        for j in range(1, k + 1):   # a jump's steps: totals interpolated, levels as reached
            step += 1
            used[owner[(cid, p)]] += 1
            res.totals.append(cur + (new - cur) * j / k)
            res.picks.append((gd.char_name(cid), gd.item_name(p), lv - k + j))
            if progress:
                progress(f"  [{team.name}] {step}/{budget}: {gd.char_name(cid)} {gd.item_name(p)} Lv{lv - k + j}  "
                         f"total {res.totals[-1] / res.base_total:.3f}x pinks-only")
        cur = new
        build = build.with_potential(cid, p, lv)
    res.build = build
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare teams at an equal potential-level budget")
    ap.add_argument("teams", nargs="+")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--max-level", type=int, default=6)
    ap.add_argument("--split", default="", help="per-member level budgets in team order, e.g. 30,15,15 (main first)")
    ap.add_argument("--total", type=int, default=None,
                    help="with --split: a shared budget; the split values become per-member caps (e.g. --total 60 --split 30,20,20)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    gd = GameData()
    out = []
    for path in a.teams:
        t0 = time.time()
        team = load_team(gd, path)
        split = [int(x) for x in a.split.split(",")] if a.split else None
        r = greedy_build(gd, team, a.budget, a.max_level, None if a.quiet else (lambda s: print(s, flush=True)), split,
                         a.total)
        out.append(r)
        print(f"{team.name}: done in {time.time() - t0:.0f}s", flush=True)
    ref = out[0]
    total = sum(int(x) for x in a.split.split(",")) if a.split else a.budget
    if a.split and a.total is not None:
        total = min(total, a.total)
    checkpoints = [n for n in (0, 10, 20, 30, 40, 50, 60, 80, 100) if n <= total]
    print(f"\nTotal damage at N potential levels (vs {ref.team} at the same N):")
    print("  " + "team".ljust(28) + "".join(f"{('N=' + str(n)):>12}" for n in checkpoints))
    for r in out:
        cells = []
        for n in checkpoints:
            tot = r.base_total if n == 0 else r.totals[min(n, len(r.totals)) - 1]
            rt = ref.base_total if n == 0 else ref.totals[min(n, len(ref.totals)) - 1]
            cells.append(f"{tot / 1e6:7.1f}M {tot / rt:4.0%}" if r is not ref else f"{tot / 1e6:7.1f}M     ")
        print("  " + r.team.ljust(28) + "".join(f"{c:>12}" for c in cells))
    for r in out:
        lv = {}
        for who, name, l in r.picks:
            lv[(who, name)] = l
        how = (f", caps {a.split}" if a.total is not None else f", split {a.split}") if a.split else ""
        print(f"\n{r.team} build ({total} levels{how}, max Lv{a.max_level}):")
        for (who, name), l in sorted(lv.items(), key=lambda x: (x[0][0], -x[1])):
            print(f"  {who:14s} {name:38s} Lv{l}")


if __name__ == "__main__":
    main()
