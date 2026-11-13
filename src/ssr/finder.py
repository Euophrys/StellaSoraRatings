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

import copy
from itertools import combinations

from .data import GameData
from .game import potential_pools
from .kit import SPECS, role_status

ROLES = ("main", "support", "any")


def element_of(gd: GameData, char_id: int) -> int:
    return gd.table("Character")[str(char_id)]["EET"]


def _has_kit(cid: int, role: str) -> bool:
    return role_status(SPECS / f"{cid}.yaml", role) not in ("missing", "stub")


def _candidates(gd: GameData, element: int) -> list[int]:
    from .web.catalog import trekker_ids
    chars = gd.table("Character")
    return [c for c in trekker_ids() if str(c) in chars and element_of(gd, c) == element]


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
            pools = potential_pools(gd, cid, role)
            have |= {gd.item_name(p) for p in pools["normal"] + pools["common"]}
        ref["include"] = [n for n in ref["include"] if n in have]
    return doc


def team_docs(gd: GameData, template: dict, trekker: str, role: str = "main", exclude=()) -> list[dict]:
    """One team document per candidate team: `trekker` in `role` ("main", "support" or "any") with every pair of
    same-element Trekkers that have a kit for the slot they'd fill. Main first; supports ordered by char id."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}, not {role!r}")
    try:
        cid = gd.find_char(trekker)
    except KeyError as e:
        raise ValueError(f"unknown trekker {trekker!r}") from e
    roles = ("main", "support") if role == "any" else (role,)
    if not any(_has_kit(cid, r) for r in roles):
        raise ValueError(f"{trekker} has no {role} kit")
    skip = {gd.find_char(n) for n in exclude}
    others = [c for c in _candidates(gd, element_of(gd, cid)) if c != cid and c not in skip]
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
