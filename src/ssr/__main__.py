"""CLI: python -m ssr teams/<team>.yaml -o out/"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .data import GameData, DEFAULT_DATA_ROOT
from .enemies import enemy_summary
from .rate import build_reference, rate_discs, rate_emblems, rate_potentials
from .report import write_xlsx
from .sim import simulate
from .team import Build, load_team


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="ssr", description="Stella Sora team ratings")
    ap.add_argument("team", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("out"))
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument("--pinks", nargs="*", metavar="TREKKER",
                    help="search pink pairs instead of rating: the named members in order (default: the main); "
                         "members not named keep their team-file pinks")
    a = ap.parse_args(argv)
    gd = GameData(a.data)
    team = load_team(gd, a.team)
    t0 = time.time()
    if a.pinks is not None:
        _pinks(gd, team, a.pinks, t0)
        return

    print(f"[{team.name}] rating discs ...", flush=True)
    discs = rate_discs(gd, team)
    print("rating emblems ...", flush=True)
    emblems = rate_emblems(gd, team, Build())
    base = Build()
    if any(m.emblems for m in team.members):
        print("(chosen emblem lines are in the baseline for potentials)")
    print("building reference ...", flush=True)
    ref = build_reference(gd, team, base)
    print("rating potentials ...", flush=True)
    pots = rate_potentials(gd, team, ref)
    baseline = simulate(gd, team, base)
    print(f"Enemy: {enemy_summary(team.enemy)}; fight {team.fight_length:g} s")
    print(f"Baseline: {baseline.total / 1e6:,.1f}M, {len(baseline.breaks)} breaks ({baseline.broken_time:.0f} s broken)")

    out = a.out / f"{team.name}.xlsx"
    write_xlsx(out, gd, team, discs, emblems, pots, baseline)
    print(f"\nwrote {out} in {time.time() - t0:.0f}s\n")

    print("Top 10 discs (main C1 / C6, support C1 / C6):")
    for r in discs[:10]:
        print(f"  {r.name:32s} {r.main_c1:7.1%} {r.main_c6:7.1%}   {r.support_c1:6.1%} {r.support_c6:6.1%}")
    print("\nReference build:", ", ".join(f"{gd.item_name(p)} Lv{lv}" for (_, p), lv in ref.potentials.items()))
    print("\nTop 10 potentials (Lv6 gain):")
    i6 = 5
    for r in sorted(pots, key=lambda r: -r.gains[i6])[:10]:
        print(f"  {gd.char_name(r.char_id):16s} {r.name:34s} {r.gains[i6]:7.2%}{'  (in ref)' if r.in_reference else ''}")


def _pinks(gd, team, names: list[str], t0: float) -> None:
    from .builds import search_pinks
    idx = {gd.char_name(m.char_id): i for i, m in enumerate(team.members)}
    try:
        members = [idx[n] if n in idx else int(n) for n in names] or [0]
    except ValueError:
        raise SystemExit(f"unknown member in {names}; team has {list(idx)}")

    def progress(i, pair):
        print(f"  {gd.char_name(team.members[i].char_id)}: {' + '.join(gd.item_name(p) for p in pair)} ...", flush=True)

    _, results = search_pinks(gd, team, members, progress)
    for i, rows in results.items():
        m = team.members[i]
        best_own = rows[0].total_own_discs
        best_team = max(r.total_team_discs for r in rows)
        print(f"\n{gd.char_name(m.char_id)} ({m.role}) pink pairs, % of best (team discs | own discs):")
        for r in rows:
            print(f"  {' + '.join(r.names):58s} {r.total_team_discs / best_team:7.1%} {r.total_own_discs / best_own:7.1%}")
            pots = ", ".join(f"{gd.item_name(p)}" for (c, p) in r.reference if c == m.char_id)
            discs = ", ".join(gd.item_name(d) for d, _ in r.own_discs)
            print(f"      ref: {pots}")
            if m.role == "main":
                print(f"      discs: {discs}")
    print(f"\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
