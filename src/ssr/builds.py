"""Pink (core potential) build search: score every 2-of-4 pink pair for a member.

Each pair is scored by its best reachable fight: the greedy reference build of normal
potentials (`build_reference`) on top of the pinks. It's scored twice, with the team file's
discs and with the top main discs re-picked for that pair, because a lineup chosen for one
build handicaps the others.

Searching every member jointly is 6^n reference builds, so members are searched one at a
time (coordinate search): each searched member's best pair is kept before the next member
is searched. Members not named keep their team-file pinks.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import combinations

from .data import GameData
from .game import potential_pools
from .parallel import simulate_many
from .rate import ALL_FILLER, build_reference, gain
from .sim import simulate
from .team import Build, TeamConfig


@dataclass
class PinkBuildRow:
    member: int
    pinks: tuple[int, ...]
    names: tuple[str, ...]
    total_team_discs: float
    total_own_discs: float
    own_discs: list[tuple[int, int]]
    reference: dict = field(default_factory=dict)   # (char_id, potential_id) -> level, own-disc run


def with_pinks(team: TeamConfig, member: int, pinks: list[int]) -> TeamConfig:
    members = list(team.members)
    members[member] = replace(members[member], pinks=list(pinks))
    return replace(team, members=members)


def pink_pairs(gd: GameData, team: TeamConfig, member: int) -> list[tuple[int, ...]]:
    m = team.members[member]
    return list(combinations(potential_pools(gd, m.char_id, m.role)["pink"], 2))


def best_main_discs(gd: GameData, team: TeamConfig, n: int = 3, copies: int = 1,
                    disc_ids: list[int] | None = None) -> list[tuple[int, int]]:
    """Top-n main discs, each rated alone (C`copies`) against all-filler discs, pinks only."""
    if disc_ids is None:
        disc_ids = sorted(int(k) for k, v in gd.table("Disc").items() if v.get("Available") and v.get("Visible"))
    fill = ALL_FILLER[0][0]
    results = simulate_many(gd, team, [dict(build=Build(), emblems=False, discs=ALL_FILLER)] + [
        dict(build=Build(), emblems=False, discs=([(d, copies), fill, fill], ALL_FILLER[1])) for d in disc_ids])
    base = results[0]
    scored = [(gain(base, r), d) for r, d in zip(results[1:], disc_ids)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [(d, copies) for _, d in scored[:n]]


def score_pinks(gd: GameData, team: TeamConfig, member: int, pinks: tuple[int, ...],
                disc_ids: list[int] | None = None, own_discs: bool = True) -> PinkBuildRow:
    """own_discs=False: score with the team file's discs only (never re-pick main discs)."""
    t = with_pinks(team, member, list(pinks))
    ref_team = build_reference(gd, t, Build())
    total_team = simulate(gd, t, ref_team).total
    if own_discs and team.members[member].role == "main":
        own = best_main_discs(gd, t, n=len(team.discs_main) or 3, disc_ids=disc_ids)
        t_own = replace(t, discs_main=own)
        ref_own = build_reference(gd, t_own, Build())
        total_own = simulate(gd, t_own, ref_own).total
    else:   # supports' pinks don't change which main discs are best enough to re-pick
        own, ref_own, total_own = list(team.discs_main), ref_team, total_team
    return PinkBuildRow(member, pinks, tuple(gd.item_name(p) for p in pinks),
                        total_team, total_own, own, dict(ref_own.potentials))


def search_pinks(gd: GameData, team: TeamConfig, members: list[int], progress=None,
                 disc_ids: list[int] | None = None) -> tuple[TeamConfig, dict[int, list[PinkBuildRow]]]:
    """Search each member in order; returns the team with the winning pinks and all rows per member."""
    results: dict[int, list[PinkBuildRow]] = {}
    for i in members:
        rows = []
        for pair in pink_pairs(gd, team, i):
            if progress:
                progress(i, pair)
            rows.append(score_pinks(gd, team, i, pair, disc_ids))
        rows.sort(key=lambda r: -r.total_own_discs)
        results[i] = rows
        team = with_pinks(team, i, list(rows[0].pinks))
        if team.members[i].role == "main":
            team = replace(team, discs_main=rows[0].own_discs)
    return team, results
