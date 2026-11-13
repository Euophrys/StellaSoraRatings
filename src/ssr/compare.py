"""Cross-team comparison: give each team the same budget of potential levels and compare total damage.

Damage shares only say how a team's damage splits; totals are comparable across teams because every team runs
through the same simulator (enemy, fight length, skill levels, stat model). Each team gets its pinks for free,
then a greedy build: every step adds +1 level to whichever normal/common potential (any member) raises team
damage the most, up to `max_level` per potential. Each step also tries jumping a potential straight to its cap and
takes the jump if it gains more per level spent (values that come in steps, e.g. Observer Array's turret limit).

    python -m ssr.compare teams/a.yaml teams/b.yaml --budget 60 --max-level 6

With `--emblems <tier>`, each team's emblems are then filled greedily on top of that build (`greedy_emblems`).

`--pin "Nazuna:Touch of Nature=6"` starts the build with that potential at that level (it counts toward the budget
and the member's cap, and the greedy can still raise it); `--pin-emblem "Gerie:Mark DMG=3"` puts that emblem line
in that many emblems before the greedy fill. Both repeat, and apply to every team with that Trekker.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field

from .data import GameData
from .emblems import SLOT_LEVEL, emblem_options, line_relevant
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
                 progress=None, split: list[int] | None = None, total: int | None = None,
                 pins: dict[tuple[int, int], int] | None = None) -> GreedyResult:
    """split: per-member level caps in team order (e.g. [30, 15, 15]). The budget is their sum, or `total` when given
    (a shared pool the members draw from up to their caps, e.g. total 60 with caps 30/20/20).

    pins: {(char_id, potential_id): level} the build starts with. They are spent first, as the first steps (totals
    interpolated, as for a jump), and count toward the budget and the owner's cap. The greedy can raise them further."""
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
    if pins:
        for (cid, p), lv in pins.items():
            if (cid, p) not in owner:
                raise KeyError(f"pin {gd.item_name(p)!r}: not a normal/common potential of {gd.char_name(cid)} here")
            build = build.with_potential(cid, p, lv)
        pinned = simulate(gd, team, build).total
        k = sum(pins.values())
        if k > budget:
            raise ValueError(f"pins spend {k} levels, more than the budget ({budget})")
        j = 0
        for (cid, p), lv in pins.items():
            used[owner[(cid, p)]] += lv
            if split and used[owner[(cid, p)]] > split[owner[(cid, p)]]:
                raise ValueError(f"pins on {gd.char_name(cid)} exceed the member's cap")
            for level in range(1, lv + 1):
                j += 1
                step += 1
                res.totals.append(cur + (pinned - cur) * j / k)
                res.picks.append((gd.char_name(cid), gd.item_name(p), level))
        cur = pinned
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


COLOUR_RANK = {"green": 0, "blue": 1, "yellow": 2, "purple": 3}


@dataclass
class EmblemResult:
    team: str
    base_total: float                       # the build, no emblems
    totals: list[float] = field(default_factory=list)   # total after each line
    slots: dict = field(default_factory=dict)   # member -> {slot: [(line name, tier label)]}
    extra: list = field(default_factory=list)   # [(member, line)] for simulate's `extra`


def greedy_emblems(gd: GameData, team: TeamConfig, build: Build, tier: str = "purple",
                   members: list[int] | None = None, per_slot: int = 4, progress=None,
                   pins: list[tuple[int, str, int]] | None = None) -> EmblemResult:
    """Fill each member's 3 emblems (Lv70 / 80 / 90 slots, `per_slot` lines each) one line at a time: every step adds
    the line (any member) that raises team damage the most. Every line rolls at `tier` (its highest tier of that
    colour or lower: purple = the top roll, "+3" on skill / potential lines). A line appears at most once per emblem,
    and only in the slots it can roll in (skill levels Lv80, potential levels Lv90). The team file's own emblems
    are ignored.

    pins: [(member index, line name, count)]: that line goes in `count` emblems (lowest slots first) before the fill."""
    want = COLOUR_RANK[tier]
    members = list(range(len(team.members))) if members is None else members
    opts = {}
    for i in members:
        m = team.members[i]
        element = gd.table("Character")[str(m.char_id)]["EET"]
        for o in emblem_options(gd, m.char_id):
            tiers = [t for t in o.tiers if COLOUR_RANK.get(t.colour, 0) <= want]
            if tiers and line_relevant(tiers[-1].line, element, m.role):
                opts[(i, o.name)] = (o, tiers[-1])
    slots = {i: {1: [], 2: [], 3: []} for i in members}
    extra: list = []
    cur = simulate(gd, team, build, emblems=False).total
    res = EmblemResult(team.name, cur)
    total_lines = per_slot * 3 * len(members)
    for i, name, count in pins or []:
        if (i, name) not in opts:
            raise KeyError(f"emblem pin {name!r}: not a line {gd.char_name(team.members[i].char_id)} can use")
        o, t = opts[(i, name)]
        for _ in range(count):
            free = [s for s in sorted(o.slots) if len(slots[i][s]) < per_slot and name not in slots[i][s]]
            if not free:
                raise ValueError(f"emblem pin {name!r} x{count}: no free emblem left for it")
            extra.append((i, t.line))
            slots[i][free[0]].append(name)
    if extra:
        cur = simulate(gd, team, build, emblems=False, extra=extra).total
        res.totals.extend([cur] * len(extra))
    for step in range(len(extra), total_lines):
        todo = []
        for (i, name), (o, t) in opts.items():
            # the lowest slot it can roll in that has room and doesn't have it yet (stat lines fill Lv70 first,
            # keeping Lv80 / 90 room for skill / potential lines)
            free = [s for s in sorted(o.slots) if len(slots[i][s]) < per_slot and name not in slots[i][s]]
            if free:
                todo.append((i, name, free[0], t))
        if not todo:
            break
        results = simulate_many(gd, team, [dict(build=build, emblems=False, extra=extra + [(i, t.line)])
                                           for i, _, _, t in todo])
        best = max(zip(todo, results), key=lambda x: x[1].total)   # first of equal totals wins
        (i, name, s, t), r = best
        if r.total <= cur * (1 + 1e-9):
            break   # nothing left adds damage
        cur = r.total
        extra.append((i, t.line))
        slots[i][s].append(name)
        res.totals.append(cur)
        if progress:
            progress(f"  [{team.name}] emblem {step + 1}/{total_lines}: {gd.char_name(team.members[i].char_id)} "
                     f"Lv{SLOT_LEVEL[s]} {name} {t.label}  total {cur / res.base_total:.3f}x")
    res.slots = {i: {s: [(n, opts[(i, n)][1].label) for n in names] for s, names in sl.items()}
                 for i, sl in slots.items()}
    res.extra = extra
    return res


def _parse_pin(s: str) -> tuple[str, str, int]:
    """'Trekker:Name=N' -> (trekker, name, N)."""
    who, _, rest = s.partition(":")
    name, _, n = rest.rpartition("=")
    if not who or not name or not n.isdigit():
        raise SystemExit(f"bad pin {s!r}: expected TREKKER:NAME=N")
    return who.strip(), name.strip(), int(n)


def _member(gd: GameData, team: TeamConfig, who: str) -> int | None:
    for i, m in enumerate(team.members):
        if gd.char_name(m.char_id).lower() == who.lower():
            return i
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare teams at an equal potential-level budget")
    ap.add_argument("teams", nargs="+")
    ap.add_argument("--budget", type=int, default=60)
    ap.add_argument("--max-level", type=int, default=6)
    ap.add_argument("--split", default="", help="per-member level budgets in team order, e.g. 30,15,15 (main first)")
    ap.add_argument("--total", type=int, default=None,
                    help="with --split: a shared budget; the split values become per-member caps (e.g. --total 60 --split 30,20,20)")
    ap.add_argument("--emblems", choices=sorted(COLOUR_RANK, key=COLOUR_RANK.get), default=None,
                    help="also fill every member's emblems greedily, every line at this tier (e.g. purple)")
    ap.add_argument("--pin", action="append", default=[], metavar="TREKKER:POTENTIAL=LEVEL",
                    help='start the build with this potential level, e.g. "Nazuna:Touch of Nature=6" (repeatable)')
    ap.add_argument("--pin-emblem", action="append", default=[], metavar="TREKKER:LINE=COUNT",
                    help='put this emblem line in COUNT emblems before the fill, e.g. "Gerie:Mark DMG=3" (repeatable)')
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    gd = GameData()
    out = []
    emb: list[EmblemResult] = []
    for path in a.teams:
        t0 = time.time()
        team = load_team(gd, path)
        split = [int(x) for x in a.split.split(",")] if a.split else None
        pins = {}
        for who, name, lv in map(_parse_pin, a.pin):
            i = _member(gd, team, who)
            if i is None:
                print(f"{team.name}: no {who}, pin {name!r} skipped", flush=True)
                continue
            m = team.members[i]
            pools = potential_pools(gd, m.char_id, m.role)
            by_name = {gd.item_name(p): p for p in pools["normal"] + pools["common"]}
            if name not in by_name:
                raise SystemExit(f"--pin {name!r}: not a {m.role} potential of {who}; have {sorted(by_name)}")
            pins[(m.char_id, by_name[name])] = lv
        epins = []
        for who, name, n in map(_parse_pin, a.pin_emblem):
            i = _member(gd, team, who)
            if i is None:
                print(f"{team.name}: no {who}, emblem pin {name!r} skipped", flush=True)
                continue
            epins.append((i, name, n))
        r = greedy_build(gd, team, a.budget, a.max_level, None if a.quiet else (lambda s: print(s, flush=True)), split,
                         a.total, pins=pins)
        out.append(r)
        if a.emblems:
            emb.append(greedy_emblems(gd, team, r.build, a.emblems,
                                      progress=None if a.quiet else (lambda s: print(s, flush=True)), pins=epins))
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

    if emb:
        print(f"\nWith emblems ({a.emblems} lines, greedy on top of the {total}-level build; vs {emb[0].team}):")
        for e in emb:
            final = e.totals[-1] if e.totals else e.base_total
            ref_final = emb[0].totals[-1] if emb[0].totals else emb[0].base_total
            print(f"  {e.team.ljust(34)} {e.base_total / 1e6:8.1f}M -> {final / 1e6:8.1f}M  "
                  f"(x{final / e.base_total:.2f}, {final / ref_final:4.0%})")
        for e, path in zip(emb, a.teams):
            team = load_team(gd, path)
            print(f"\n{e.team} emblems:")
            for i, sl in e.slots.items():
                for s_, lines in sl.items():
                    if lines:
                        print(f"  {gd.char_name(team.members[i].char_id):18s} Lv{SLOT_LEVEL[s_]}: "
                              + ", ".join(f"{n} {lab}" for n, lab in lines))


if __name__ == "__main__":
    main()
