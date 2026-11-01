"""Cross-team comparison: give each team the same budget of potential levels and compare total damage.

Damage shares only say how a team's damage splits; totals are comparable across teams because every team runs
through the same simulator (enemy, fight length, skill levels, stat model). Each team gets its pinks for free,
then a greedy build: every step adds +1 level to whichever normal/common potential (any member) raises team
damage the most, up to `max_level` per potential.

    python -m ssr.compare teams/a.yaml teams/b.yaml --budget 60 --max-level 6
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field

from .data import GameData
from .game import potential_pools
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
                 progress=None, split: list[int] | None = None) -> GreedyResult:
    """split: per-member level budgets in team order (e.g. [30, 15, 15]); budget is then their sum."""
    cands = []
    owner = {}
    for i, m in enumerate(team.members):
        pools = potential_pools(gd, m.char_id, m.role)
        for p in pools["normal"] + pools["common"]:
            cands.append((m.char_id, p))
            owner[(m.char_id, p)] = i
    if split:
        budget = sum(split)
    used = [0] * len(team.members)
    build = Build()
    cur = simulate(gd, team, build).total
    res = GreedyResult(team.name, cur, build=build)
    for step in range(budget):
        best = None
        for cid, p in cands:
            lv = build.potentials.get((cid, p), 0)
            if lv >= max_level or (split and used[owner[(cid, p)]] >= split[owner[(cid, p)]]):
                continue
            tot = simulate(gd, team, build.with_potential(cid, p, lv + 1)).total
            if best is None or tot > best[0]:
                best = (tot, cid, p, lv + 1)
        if best is None:
            break
        cur, cid, p, lv = best
        build = build.with_potential(cid, p, lv)
        used[owner[(cid, p)]] += 1
        res.totals.append(cur)
        res.picks.append((gd.char_name(cid), gd.item_name(p), lv))
        if progress:
            progress(f"  [{team.name}] {step + 1}/{budget}: {gd.char_name(cid)} {gd.item_name(p)} Lv{lv}  "
                     f"total {cur / res.base_total:.3f}x pinks-only")
    res.build = build
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare teams at an equal potential-level budget")
    ap.add_argument("teams", nargs="+")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--max-level", type=int, default=6)
    ap.add_argument("--split", default="", help="per-member level budgets in team order, e.g. 30,15,15 (main first)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    gd = GameData()
    out = []
    for path in a.teams:
        t0 = time.time()
        team = load_team(gd, path)
        split = [int(x) for x in a.split.split(",")] if a.split else None
        r = greedy_build(gd, team, a.budget, a.max_level, None if a.quiet else (lambda s: print(s, flush=True)), split)
        out.append(r)
        print(f"{team.name}: done in {time.time() - t0:.0f}s", flush=True)
    ref = out[0]
    total = sum(int(x) for x in a.split.split(",")) if a.split else a.budget
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
        print(f"\n{r.team} build ({total} levels{', split ' + a.split if a.split else ''}, max Lv{a.max_level}):")
        for (who, name), l in sorted(lv.items(), key=lambda x: (x[0][0], -x[1])):
            print(f"  {who:14s} {name:38s} Lv{l}")


if __name__ == "__main__":
    main()
