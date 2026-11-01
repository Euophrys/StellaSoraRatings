"""Team config (YAML) and immutable builds."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .data import GameData, REPO_ROOT
from .formula import Enemy
from .kit import Kit, SPECS, load_kit, pink_ids
from .emblems import (EmblemChargeEfficiency, EmblemLine, EmblemPotentialLevel, EmblemSkillLevel,  # noqa: F401 (re-export)
                      _SKILL_SLOTS, emblem_lines)

TEAMS = REPO_ROOT / "teams"
FILLER = 0   # stats-only filler disc (Eternal Brilliance stats, Lv90 C6, no effects)
FILLER_SOURCE_DISC = 214067


@dataclass
class MemberConfig:
    char_id: int
    role: str
    pinks: list[int]
    skill_levels: dict[str, int]
    emblems: list
    kit: Kit
    talents: int = 0   # talent groups unlocked (dupes): T0 = 0, T1 = 1, ...


@dataclass
class TeamConfig:
    name: str
    members: list[MemberConfig]
    enemy: Enemy
    fight_length: float = 120.0
    tick: float = 0.05
    mark_icd: float = 1.0
    discs_main: list[tuple[int, int]] = field(default_factory=list)
    discs_support: list[tuple[int, int]] = field(default_factory=list)
    reference: dict = field(default_factory=lambda: dict(steps=2, main_picks=2, support_picks=1, level=6))
    assumptions: dict = field(default_factory=lambda: dict(unknown_trigger_uptime=1.0, disc_stats_target="team"))


@dataclass(frozen=True)
class Build:
    potentials: dict = field(default_factory=dict)   # (char_id, potential_id) -> level

    def with_potential(self, char_id: int, potential_id: int, level: int) -> "Build":
        return Build({**self.potentials, (char_id, potential_id): level})

    def without(self, char_id: int, potential_id: int) -> "Build":
        return Build({k: v for k, v in self.potentials.items() if k != (char_id, potential_id)})

    def levels_for(self, char_id: int) -> dict[int, int]:
        return {p: lv for (c, p), lv in self.potentials.items() if c == char_id}


def _disc(gd: GameData, d) -> tuple[int, int]:
    if d == "filler" or (isinstance(d, dict) and d.get("name") == "filler"):
        return (FILLER, 6)
    did = gd.find_item(d["name"], prefix=bool(d.get("prefix")), within="Disc")
    return (did, int(d.get("copies", 1)))


def _emblem(lines_by_name: dict, name: str):
    if name not in lines_by_name:
        raise KeyError(f"unknown emblem line {name!r}; known: {sorted(lines_by_name)}")
    return lines_by_name[name]


def load_team(gd: GameData, path: Path, specs: Path = SPECS) -> TeamConfig:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    lines = {l.name: l for l in emblem_lines(gd)}
    members = []
    for m in doc["members"]:
        cid = gd.find_char(m["trekker"])
        role = m["role"]
        members.append(MemberConfig(
            char_id=cid, role=role, pinks=pink_ids(gd, cid, m.get("pinks", []), role),
            skill_levels={"auto": 10, "skill": 10, "ult": 10, **(m.get("skill_levels") or {})},
            emblems=[_emblem(lines, n) for n in m.get("emblems", [])],
            kit=load_kit(gd, specs / f"{cid}.yaml", role),
            talents=int(m.get("talents", 0)),
        ))
    e = doc.get("enemy", {})
    return TeamConfig(
        name=doc.get("name", Path(path).stem), members=members,
        enemy=Enemy(res=float(e.get("res", 250)), defense=float(e.get("defense", 0)), broken=float(e.get("broken", 1.0))),
        fight_length=float(doc.get("fight_length", 120)), tick=float(doc.get("tick", 0.05)),
        mark_icd=float(doc.get("mark_icd", 1.0)),
        discs_main=[_disc(gd, d) for d in doc["discs"]["main"]],
        discs_support=[_disc(gd, d) for d in doc["discs"]["support"]],
        reference={**dict(steps=2, main_picks=2, support_picks=1, level=6), **(doc.get("reference") or {})},
        assumptions={**dict(unknown_trigger_uptime=1.0, disc_stats_target="team"), **(doc.get("assumptions") or {})},
    )
