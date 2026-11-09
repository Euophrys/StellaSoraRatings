"""Accessors for characters, skills, hits, discs and potential pools."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .data import GameData
from .stats import (StatBlock, ATK, DEF, HP, CRIT_RATE, CRIT_DMG, AUTO_DMG, SKILL_DMG, ULT_DMG,
                    ELEM_DMG_BASE, elem_stat)

_ROLE_SKILL_FIELDS = {
    "main": {"auto": "NormalAtkId", "skill": "SkillId", "ult": "UltimateId"},
    "support": {"auto": "AssistNormalAtkId", "skill": "AssistSkillId", "ult": "AssistUltimateId"},
}


_ATTR_GROUPS: dict = {}   # id(gd) -> (gd, {GroupId: [Attribute rows]}): the table is big, and every simulate asks


def _attr_rows(gd: GameData, group_id: int) -> list[dict]:
    hit = _ATTR_GROUPS.get(id(gd))
    if hit is None or hit[0] is not gd:
        groups: dict = {}
        for r in gd.table("Attribute").values():
            groups.setdefault(r.get("GroupId"), []).append(r)
        hit = _ATTR_GROUPS[id(gd)] = (gd, groups)
    return hit[1].get(group_id, [])


def char_base_stats(gd: GameData, char_id: int, level: int = 90) -> StatBlock:
    rows = [r for r in _attr_rows(gd, char_id) if r.get("lvl") == level]
    if not rows:
        raise KeyError(f"no Attribute rows for char {char_id} lvl {level}")
    r = max(rows, key=lambda r: r.get("Break", 0))
    s = StatBlock()
    s.set_base(ATK, r.get("Atk", 0))
    s.set_base(DEF, r.get("Def", 0))
    s.set_base(HP, r.get("Hp", 0))
    s.add_stat(CRIT_RATE, r.get("CritRate", 0) / 10000)
    s.add_stat(CRIT_DMG, r.get("CritPower", 0) / 10000)
    return s


def toughness_adjust(gd: GameData, char_id: int) -> float:
    """The Trekker's resilience-damage multiplier (`Attribute.ToughnessDamageAdjust`/10000), 1.0 if absent."""
    vals = [r["ToughnessDamageAdjust"] for r in _attr_rows(gd, char_id) if r.get("ToughnessDamageAdjust")]
    return max(vals) / 10000 if vals else 1.0


def skill_ids(gd: GameData, char_id: int, role: str) -> dict[str, int]:
    c = gd.table("Character")[str(char_id)]
    return {k: c[f] for k, f in _ROLE_SKILL_FIELDS[role].items()}


def skill_cd(gd: GameData, skill_id: int) -> float:
    return gd.table("Skill")[str(skill_id)].get("SkillCD", 0) / 10000


def ult_energy(gd: GameData, skill_id: int) -> float:
    return gd.table("Skill")[str(skill_id)].get("UltraEnergy", 0) / 10000


@dataclass(frozen=True)
class Hit:
    id: int
    damage_type: int
    element: int
    base_stat: int
    source_type: int
    pct: tuple[float, ...]
    energy: float = 0.0
    level_type: int | None = None
    level_data: int | None = None


def hit(gd: GameData, hit_id: int) -> Hit:
    r = gd.table("HitDamage")[str(hit_id)]
    return Hit(
        id=hit_id,
        damage_type=r.get("DamageType", 1),
        element=r.get("ElementType", 0),
        base_stat=HP if r.get("DamageBonusType") == 3 else ATK,
        source_type=r.get("SourceType", 0),
        pct=tuple(x * 1e-6 for x in r.get("SkillPercentAmend", [0])),
        energy=r.get("EnergyCharge", 0) / 10000,
        level_type=r.get("levelTypeData"),
        level_data=r.get("LevelData"),
    )


_LEVEL_SLOT = {5: "auto", 2: "skill", 1: "skill", 4: "ult"}


def hit_level(h: Hit, skill_levels: dict[str, int], potential_levels: dict[int, int], fallback: str = "skill") -> int:
    """Index into SkillPercentAmend, per HitDamage.levelTypeData (see docs/assumptions.md)."""
    if h.level_type == 1:
        return potential_levels.get(h.level_data, 1)
    if h.level_type == 3:
        return skill_levels.get(_LEVEL_SLOT.get(h.level_data, fallback), 10)
    if h.level_type == 4:
        return 9
    if h.level_type is None:
        return skill_levels.get(fallback, 10)
    return 1


@lru_cache(maxsize=None)
def _last_real(pct: tuple[float, ...]) -> int:
    return max((i for i, x in enumerate(pct) if x), default=0) + 1


def hit_pct(h: Hit, skill_level: int) -> float:
    """Multiplier at `skill_level`, clamped to the last real (non-zero) entry: many arrays are zero-padded."""
    return h.pct[max(1, min(skill_level, _last_real(h.pct))) - 1]


def disc_base_stats(gd: GameData, disc_id: int, level: int = 90, copies: int = 1) -> StatBlock:
    d = gd.table("Disc")[str(disc_id)]
    rows = [r for r in gd.table("Attribute").values()
            if r.get("GroupId") == d["AttrBaseGroupId"] and r.get("lvl") == level]
    r = max(rows, key=lambda r: r.get("Break", 0))
    s = StatBlock()
    for stat, key in ((ATK, "Atk"), (DEF, "Def"), (HP, "Hp")):
        s.flat[stat] += r.get(key, 0)
    for key, stat in DISC_PCT_FIELDS.items():
        if key in r:
            s.add_stat(stat, r[key] / 10000)
    if copies > 1:
        extra = [x for x in gd.table("DiscExtraAttribute").values()
                 if x.get("GroupId") == d.get("AttrExtraGroupId") and x.get("Break") == copies - 1]
        for x in extra:
            for stat, key in ((ATK, "Atk"), (DEF, "Def"), (HP, "Hp")):
                s.flat[stat] += x.get(key, 0)
    return s


# Attribute columns that discs use as a percentage substat (value / 10000).
# Element order W,F,S,A,L,D = Aqua, Ignis, Terra, Ventus, Lux, Umbra.
DISC_PCT_FIELDS = {
    **{f"{c}EE": elem_stat(ELEM_DMG_BASE, i + 1) for i, c in enumerate("WFSALD")},
    "NORMALDMG": AUTO_DMG, "SKILLDMG": SKILL_DMG, "ULTRADMG": ULT_DMG,
}


def potential_pools(gd: GameData, char_id: int, role: str) -> dict[str, list[int]]:
    c = gd.table("CharPotential")[str(char_id)]
    pre = "Master" if role == "main" else "Assist"
    return {
        "pink": list(c.get(f"{pre}SpecificPotentialIds", [])),
        "normal": list(c.get(f"{pre}NormalPotentialIds", [])),
        "common": list(c.get("CommonPotentialIds", [])),
    }


def talent_groups(gd: GameData, char_id: int) -> list[dict]:
    """A Trekker's talent groups in unlock order (each dupe unlocks the next; `PreGroup` chains them)."""
    groups = {g["Id"]: g for g in gd.table("TalentGroup").values() if g.get("CharId") == char_id}
    out, prev = [], None
    while True:
        nxt = [g for g in groups.values() if g.get("PreGroup") == prev]
        if not nxt:
            return out
        out.append(nxt[0])
        prev = nxt[0]["Id"]


def talent_nodes(gd: GameData, char_id: int, n_groups: int) -> tuple[list[int], list[int]]:
    """(stat effect ids, key talent ids) of the first `n_groups` talent groups.

    Type 2 nodes are plain stat effects (read from data); Type 1 is the group's key talent, which is
    scripted and needs a `talents:` entry in the kit spec."""
    effects, keys = [], []
    for g in talent_groups(gd, char_id)[:n_groups]:
        for r in sorted((r for r in gd.table("Talent").values() if r.get("GroupId") == g["Id"]),
                        key=lambda r: r.get("Index", 0)):
            if r.get("Type") == 2:
                effects += list(r.get("EffectId") or [])
            elif r.get("Type") == 1:
                keys.append(r["Id"])
    return effects, keys
