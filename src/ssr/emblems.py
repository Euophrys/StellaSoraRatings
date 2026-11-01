"""Emblem (CharGem) lines: every line a trekker can roll, at every roll tier.

Data: `CharGemAttrValue`. Each row is one tier of one line: `AttrType` picks the kind (12 stat, 37 charge
efficiency, 7 skill level, 99 potential level), `Level` the tier (1 = lowest) and `Rarity` its colour
(4 green, 3 blue, 2 yellow, 1 purple). Slots: 1 = Lv70 (stat lines), 2 = Lv80 (stat + skill-level lines),
3 = Lv90 (stat + potential lines).
"""
from __future__ import annotations

from dataclasses import dataclass

from .data import GameData
from .stats import ELEM_DMG_BASE, ELEM_IGNORE_RES_BASE, ELEM_PEN_BASE, ELEM_RES_BASE, ELEM_TAKEN_BASE, stat_name

RARITY_COLOUR: dict[int, str] = {4: "green", 3: "blue", 2: "yellow", 1: "purple"}
SLOT_LEVEL = {1: 70, 2: 80, 3: 90}


@dataclass(frozen=True)
class EmblemLine:
    name: str
    stat: int
    value: float
    is_pct: bool = False


@dataclass(frozen=True)
class EmblemSkillLevel:
    name: str
    slot: str      # auto | main_skill | support_skill | ult
    plus: int

    @property
    def action(self) -> str:
        return {"auto": "auto", "main_skill": "skill", "support_skill": "skill", "ult": "ult"}[self.slot]

    def applies_to(self, role: str) -> bool:
        return not ((self.slot == "main_skill" and role != "main") or (self.slot == "support_skill" and role != "support"))


@dataclass(frozen=True)
class EmblemPotentialLevel:
    """Lv90 "+N" line: the potential fights at target + N (capped at 9); target 0 still fights at N."""
    name: str
    potential_id: int
    plus: int


@dataclass(frozen=True)
class EmblemChargeEfficiency:
    """Ult energy gain x (1 + value), only while the trekker has this role (docs/assumptions.md)."""
    name: str
    role: str      # main | support
    value: float


@dataclass(frozen=True)
class EmblemTier:
    label: str     # colour for stat lines, "+1".."+3" for skill / potential lines
    colour: str
    line: object   # EmblemLine | EmblemSkillLevel | EmblemPotentialLevel | EmblemChargeEfficiency


@dataclass(frozen=True)
class EmblemOption:
    name: str
    kind: str      # stat | skill | potential
    slots: frozenset[int]
    tiers: tuple[EmblemTier, ...]   # lowest -> highest


_SKILL_SLOTS = {1: ("auto", "Auto"), 2: ("main_skill", "Skill"), 3: ("support_skill", "Support"), 4: ("ult", "Ult")}
_ELEM_BASES = (ELEM_DMG_BASE, ELEM_PEN_BASE, ELEM_RES_BASE, ELEM_TAKEN_BASE, ELEM_IGNORE_RES_BASE)


def _elem_of(stat: int) -> int | None:
    """Element 1-6 of a per-element stat, None for other stats."""
    for b in _ELEM_BASES:
        if b <= stat < b + 6:
            return stat - b + 1
    return None


def _desc(gd: GameData, atype: int, sub1, sub2) -> str:
    r = gd.table("EffectDesc").get(str(atype * 10000 + (sub1 or 0) * 10 + (sub2 or 0)), {})
    v = r.get("RandomAttrDesc") or r.get("Desc") or ""
    return (gd.text(v) or v) if isinstance(v, str) else str(v)


def _stat_line_name(sub1: int, sub2) -> tuple[str, bool]:
    is_pct = sub1 in (1, 2, 3) and sub2 == 2
    return stat_name(sub1, is_pct).replace(" (flat)", ""), is_pct


def _rows(gd: GameData) -> dict[tuple, list[dict]]:
    """(AttrType, FirstSubtype, SecondSubtype, Tag) -> tier rows sorted by Level; duplicate TypeIds dropped."""
    out: dict[tuple, dict[int, dict]] = {}
    for r in gd.table("CharGemAttrValue").values():
        key = (r["AttrType"], r.get("AttrTypeFirstSubtype"), r.get("AttrTypeSecondSubtype"), r.get("Tag"))
        out.setdefault(key, {}).setdefault(r["Level"], r)
    return {k: [v[lv] for lv in sorted(v)] for k, v in out.items()}


def emblem_options(gd: GameData, char_id: int) -> list[EmblemOption]:
    """Every line this trekker can roll: per-element lines only for its own element."""
    element = gd.table("Character")[str(char_id)]["EET"]
    opts: list[EmblemOption] = []
    for (atype, sub1, sub2, tag), rows in sorted(_rows(gd).items(), key=lambda kv: tuple(x or 0 for x in kv[0])):
        if atype == 12:
            el = _elem_of(sub1)
            if el is not None and el != element:
                continue
            name, is_pct = _stat_line_name(sub1, sub2)
            tiers = tuple(EmblemTier(RARITY_COLOUR[r["Rarity"]], RARITY_COLOUR[r["Rarity"]],
                                     EmblemLine(name, sub1, float(r["Value"]), is_pct)) for r in rows)
            opts.append(EmblemOption(name, "stat", frozenset({1, 2, 3}), tiers))
        elif atype == 37:
            name = _desc(gd, atype, sub1, sub2)
            role = "main" if sub1 == 1 else "support"
            tiers = tuple(EmblemTier(RARITY_COLOUR[r["Rarity"]], RARITY_COLOUR[r["Rarity"]],
                                     EmblemChargeEfficiency(name, role, float(r["Value"]))) for r in rows)
            opts.append(EmblemOption(name, "stat", frozenset({1, 2, 3}), tiers))
        elif atype == 7 and sub1 in _SKILL_SLOTS:
            name = _desc(gd, atype, sub1, sub2)
            slot = _SKILL_SLOTS[sub1][0]
            tiers = tuple(EmblemTier(f"+{int(float(r['Value']))}", RARITY_COLOUR[r["Rarity"]],
                                     EmblemSkillLevel(name, slot, int(float(r["Value"])))) for r in rows)
            opts.append(EmblemOption(name, "skill", frozenset({2}), tiers))
        elif atype == 99:
            pid = 500000 + char_id * 100 + sub1
            if str(pid) not in gd.table("Potential"):
                continue
            name = gd.item_name(pid)
            tiers = tuple(EmblemTier(f"+{int(float(r['Value']))}", RARITY_COLOUR[r["Rarity"]],
                                     EmblemPotentialLevel(name, pid, int(float(r["Value"])))) for r in rows)
            opts.append(EmblemOption(name, "potential", frozenset({3}), tiers))
    seen: set[str] = set()
    unique = []
    for o in opts:
        if o.name not in seen:
            seen.add(o.name)
            unique.append(o)
    return unique


_OPT_CACHE: dict = {}


def _options_by_name(gd: GameData, char_id: int) -> dict[str, EmblemOption]:
    key = (id(gd), char_id)
    if key not in _OPT_CACHE:
        _OPT_CACHE[key] = {o.name: o for o in emblem_options(gd, char_id)}
    return _OPT_CACHE[key]


def find_emblem_option(gd: GameData, char_id: int, line: str) -> EmblemOption:
    opts = _options_by_name(gd, char_id)
    if line not in opts:
        raise KeyError(f"unknown emblem line {line!r} for {gd.char_name(char_id)}; known: {sorted(opts)}")
    return opts[line]


def find_emblem_tier(gd: GameData, char_id: int, line: str, tier: str) -> EmblemTier:
    opt = find_emblem_option(gd, char_id, line)
    for t in opt.tiers:
        if t.label == str(tier):
            return t
    raise KeyError(f"unknown tier {tier!r} for emblem line {line!r}; valid: {[t.label for t in opt.tiers]}")


def _potential_in_role(potential_id: int, role: str) -> bool:
    """Potential ids are 500000 + char*100 + index: 1-20 main, 21-40 support, 41+ common."""
    idx = potential_id % 100
    if idx > 40:
        return True
    return idx <= 20 if role == "main" else idx > 20


def line_relevant(line, element: int, role: str) -> bool:
    if isinstance(line, EmblemSkillLevel):
        return line.applies_to(role) and not (role == "support" and line.slot == "auto")
    if isinstance(line, EmblemPotentialLevel):
        return _potential_in_role(line.potential_id, role)
    if isinstance(line, EmblemChargeEfficiency):
        return line.role == role
    el = _elem_of(line.stat)
    return el is None or el == element


def emblem_lines(gd: GameData) -> list[EmblemLine | EmblemSkillLevel]:
    """Every emblem stat line and skill-level line at its best roll (rarity 1, highest Level)."""
    best: dict[tuple, dict] = {}
    for r in gd.table("CharGemAttrValue").values():
        if r.get("Rarity") != 1 or r.get("AttrType") not in (7, 12):
            continue
        key = (r["AttrType"], r.get("AttrTypeFirstSubtype"), r.get("AttrTypeSecondSubtype"))
        if key not in best or r["Level"] > best[key]["Level"]:
            best[key] = r
    out: list = []
    for (atype, sub1, sub2), r in sorted(best.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0, kv[0][2] or 0)):
        if atype == 12:
            name, is_pct = _stat_line_name(sub1, sub2)
            out.append(EmblemLine(name, sub1, float(r["Value"]), is_pct))
        elif sub1 in _SKILL_SLOTS:
            slot, label = _SKILL_SLOTS[sub1]
            plus = int(float(r["Value"]))
            out.append(EmblemSkillLevel(f"{label} +{plus}", slot, plus))
    return out
