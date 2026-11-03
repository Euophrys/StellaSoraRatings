"""Team config (YAML) and immutable builds."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .data import GameData, REPO_ROOT
from .formula import Enemy  # noqa: F401 (re-export)
from .enemies import enemy_from_doc, _res_by_element, _ELEMENT_IDS  # noqa: F401 (re-export)
from .kit import Kit, SPECS, load_kit, pink_ids
from .emblems import (EmblemChargeEfficiency, EmblemLine, EmblemPotentialLevel, EmblemSkillLevel,  # noqa: F401 (re-export)
                      _SKILL_SLOTS, emblem_lines, find_emblem_option, find_emblem_tier)
from .game import potential_pools

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
    targets: dict[int, int] = field(default_factory=dict)   # potential id -> target level (build guide page)
    emblem_slots: list = field(default_factory=list)        # 3 slots x [(line, tier)] as written; [] for flat lists
    level: int = 90         # Trekker level (Attribute rows)
    bonus_stats: list = field(default_factory=list)   # [(stat EAT, value, is_pct)]: flat extras, e.g. build-level ATK


@dataclass
class TeamConfig:
    name: str
    members: list[MemberConfig]
    enemy: Enemy
    fight_length: float = 120.0
    tick: float = 0.05
    mark_icd: float = 1.0
    hold: list = field(default_factory=list)   # [{member, action, until, max_wait}]: rotation timing (see specs/README.md)
    discs_main: list[tuple[int, int]] = field(default_factory=list)
    discs_support: list[tuple[int, int]] = field(default_factory=list)
    reference: dict = field(default_factory=lambda: dict(steps=2, main_picks=2, support_picks=1, level=6))
    assumptions: dict = field(default_factory=lambda: dict(unknown_trigger_uptime=1.0, disc_stats_target="team"))
    budget: list[int] = field(default_factory=lambda: [30, 15, 15])   # level budget per member (build guide page)
    max_level: int = 6
    budget_total: int | None = None   # shared level budget; `budget` then holds per-member caps
    disc_level: int = 90   # level of every disc (base stats), filler included


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


class TeamDocError(ValueError):
    """A team document names something that doesn't exist or has a bad value."""


_SLOT_KINDS = {1: {"stat"}, 2: {"stat", "skill"}, 3: {"stat", "potential"}}
_MAX_TARGET = 6


def _legacy_emblem(lines_by_name: dict, name: str):
    if name not in lines_by_name:
        raise KeyError(f"unknown emblem line {name!r}; known: {sorted(lines_by_name)}")
    return lines_by_name[name]


def _member_emblems(gd: GameData, cid: int, raw: list, lines_by_name: dict) -> tuple[list, list]:
    """(emblem lines, slots as written). Flat lists of names are the legacy top-tier format."""
    if all(isinstance(x, str) for x in raw):
        return [_legacy_emblem(lines_by_name, n) for n in raw], []
    lines, slots = [], [[], [], []]
    for e in raw:
        if not isinstance(e, dict) or e.get("slot") not in (1, 2, 3):
            raise KeyError(f"emblem entry {e!r}: needs slot 1, 2 or 3 and lines")
        slot = e["slot"]
        written = e.get("lines") or []
        if len(written) + len(slots[slot - 1]) > 4:
            raise KeyError(f"emblem slot {slot} has {len(written)} lines; at most 4")
        for ln in written:
            name, tier = ln.get("line"), str(ln.get("tier"))
            opt = find_emblem_option(gd, cid, name)
            if opt.kind not in _SLOT_KINDS[slot]:
                raise KeyError(f"emblem line {name!r} ({opt.kind}) can't roll in slot {slot} "
                               f"(Lv{70 + 10 * (slot - 1)})")
            lines.append(find_emblem_tier(gd, cid, name, tier).line)
            slots[slot - 1].append((name, tier))
    return lines, slots


def _member_targets(gd: GameData, cid: int, role: str, raw: dict) -> dict[int, int]:
    pools = potential_pools(gd, cid, role)
    by_name = {gd.item_name(p): p for p in pools["normal"] + pools["common"]}
    out = {}
    for name, lv in (raw or {}).items():
        if name not in by_name:
            raise KeyError(f"target potential {name!r} isn't a {role} potential; have {sorted(by_name)}")
        if not isinstance(lv, int) or isinstance(lv, bool) or not 0 <= lv <= _MAX_TARGET:
            raise KeyError(f"target level {lv!r} for {name!r}: must be 0-{_MAX_TARGET}")
        out[by_name[name]] = lv
    return out


def team_from_doc(gd: GameData, doc: dict, name: str = "team", specs: Path = SPECS) -> TeamConfig:
    """Parse a team document (the YAML of teams/*.yaml); raises TeamDocError naming the bad value."""
    lines = {l.name: l for l in emblem_lines(gd)}
    members = []
    for k, m in enumerate(doc.get("members") or []):
        who = m.get("trekker", f"member {k + 1}")
        try:
            cid = gd.find_char(m["trekker"])
            role = m["role"]
            emblems, slots = _member_emblems(gd, cid, m.get("emblems") or [], lines)
            members.append(MemberConfig(
                char_id=cid, role=role, pinks=pink_ids(gd, cid, m.get("pinks") or [], role),
                skill_levels={"auto": 10, "skill": 10, "ult": 10, **(m.get("skill_levels") or {})},
                emblems=emblems,
                kit=load_kit(gd, specs / f"{cid}.yaml", role),
                talents=int(m.get("talents", 0)),
                targets=_member_targets(gd, cid, role, m.get("targets")),
                emblem_slots=slots,
                level=int(m.get("level", 90)),
                bonus_stats=[(int(b["stat"]), float(b["value"]), bool(b.get("pct", False)))
                             for b in m.get("bonus_stats") or []],
            ))
        except (KeyError, ValueError, TypeError, FileNotFoundError) as e:
            msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
            if isinstance(e, FileNotFoundError):
                msg = "no kit spec for this trekker (can't be simulated)"
            raise TeamDocError(f"{who}: {msg}") from e
    try:
        enemy = enemy_from_doc(gd, doc.get("enemy") or {})
        discs = doc["discs"]
        return TeamConfig(
            name=doc.get("name", name), members=members,
            enemy=enemy,
            fight_length=float(doc.get("fight_length") or enemy.fight_length or 120), tick=float(doc.get("tick", 0.05)),
            mark_icd=float(doc.get("mark_icd", 1.0)),
            hold=[dict(h) for h in doc.get("hold") or []],
            discs_main=[_disc(gd, d) for d in discs["main"]],
            discs_support=[_disc(gd, d) for d in discs["support"]],
            reference={**dict(steps=2, main_picks=2, support_picks=1, level=6), **(doc.get("reference") or {})},
            assumptions={**dict(unknown_trigger_uptime=1.0, disc_stats_target="team"), **(doc.get("assumptions") or {})},
            budget=[int(x) for x in doc.get("budget", [30, 15, 15])],
            max_level=int(doc.get("max_level", 6)),
            budget_total=int(doc["budget_total"]) if doc.get("budget_total") is not None else None,
            disc_level=int(doc.get("disc_level", 90)),
        )
    except (KeyError, ValueError, TypeError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        raise TeamDocError(f"team: {msg}") from e


def load_team(gd: GameData, path: Path, specs: Path = SPECS) -> TeamConfig:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    return team_from_doc(gd, doc, Path(path).stem, specs)


def team_build(team: TeamConfig) -> Build:
    """The members' target levels as a Build (levels > 0 only)."""
    return Build({(m.char_id, p): lv for m in team.members for p, lv in m.targets.items() if lv > 0})


def save_team(doc: dict, path: Path) -> None:
    """Write a team document; an existing file's leading comment block is kept above the dump."""
    path = Path(path)
    header = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("#"):
                break
            header.append(line)
    body = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    path.write_text("".join(h + "\n" for h in header) + body, encoding="utf-8")
