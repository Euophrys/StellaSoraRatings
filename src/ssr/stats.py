"""Stat type enum (EAT) and additive stat blocks."""
from __future__ import annotations

from collections import defaultdict

from .data import GameData, DEFAULT_DATA_ROOT

ATK, DEF, HP = 1, 2, 3
CRIT_RATE, CRIT_DMG = 6, 8
DEF_PEN, IGNORE_DEF = 9, 10   # attacker side: effective DEF = DEF x (1 - Ignore DEF) - DEF PEN (2.def.c)
ELEM_RES_BASE = 11
ELEM_DMG_BASE = 17
ELEM_PEN_BASE = 23
ELEM_IGNORE_RES_BASE = 29
ELEM_TAKEN_BASE = 35
ATK_SPD = 47   # runs the auto string faster: its clock advances at (1 + ATK SPD)
DMG_DEALT, DMG, FINAL_DMG, FINAL_DMG2 = 49, 50, 51, 52
DMG_TAKEN, DMG_TAKEN2, VUL = 53, 54, 55
AUTO_DMG, SKILL_DMG, ULT_DMG, OTHER_DMG = 56, 57, 58, 59
AUTO_TAKEN, SKILL_TAKEN, ULT_TAKEN, OTHER_TAKEN = 60, 61, 62, 63
MARK_DMG, MARK_TAKEN, MINION_DMG, PROJ_DMG = 64, 65, 66, 68
AUTO_CRIT_RATE, SKILL_CRIT_RATE, ULT_CRIT_RATE, MARK_CRIT_RATE, MINION_CRIT_RATE, PROJ_CRIT_RATE = 70, 71, 72, 73, 74, 75
AUTO_CRIT_DMG, SKILL_CRIT_DMG, ULT_CRIT_DMG, MARK_CRIT_DMG, MINION_CRIT_DMG, PROJ_CRIT_DMG = 77, 78, 79, 80, 81, 82

ELEMENTS = {1: "Aqua", 2: "Ignis", 3: "Terra", 4: "Ventus", 5: "Lux", 6: "Umbra"}

# Hit DamageType -> slot. 7 = Minion DMG (only summoners use it; their text says "Minion DMG") — see docs/assumptions.md.
SLOT_OF_DAMAGE_TYPE = {1: "auto", 2: "skill", 3: "ult", 4: "other", 5: "mark", 7: "minion"}
SLOT_DMG = {"auto": AUTO_DMG, "skill": SKILL_DMG, "ult": ULT_DMG, "other": OTHER_DMG,
            "mark": MARK_DMG, "minion": MINION_DMG, "proj": PROJ_DMG}
SLOT_CRIT_RATE = {"auto": AUTO_CRIT_RATE, "skill": SKILL_CRIT_RATE, "ult": ULT_CRIT_RATE,
                  "mark": MARK_CRIT_RATE, "minion": MINION_CRIT_RATE, "proj": PROJ_CRIT_RATE}
SLOT_CRIT_DMG = {"auto": AUTO_CRIT_DMG, "skill": SKILL_CRIT_DMG, "ult": ULT_CRIT_DMG,
                 "mark": MARK_CRIT_DMG, "minion": MINION_CRIT_DMG, "proj": PROJ_CRIT_DMG}
SLOT_TAKEN = {"auto": AUTO_TAKEN, "skill": SKILL_TAKEN, "ult": ULT_TAKEN, "other": OTHER_TAKEN,
              "mark": MARK_TAKEN}

BASE_STATS = (ATK, DEF, HP)
DMG_MULT = 85      # "DMG Multiplier": x (1 + value) on the hit, outside the DMG buckets (docs/assumptions.md)
RES_BREAK_EFF = 43   # Resilience Break Efficiency: x (1 + value) on resilience damage dealt


def elem_stat(base: int, element: int) -> int:
    return base + element - 1


def _build_stat_names(gd: GameData) -> dict[int, str]:
    names: dict[int, str] = {}
    for row in gd.table("EffectDesc").values():
        # 12xxxx rows are the attribute family; others reuse TypeID for skill/potential levels.
        if "TypeID" in row and row["Id"] // 10000 == 12 and row["Type2ID"] == 2:
            names[row["TypeID"]] = gd.text(row["Desc"]) or f"stat {row['TypeID']}"
    return names


STAT_NAMES: dict[int, str] = _build_stat_names(GameData(DEFAULT_DATA_ROOT))
CHARGE_EFF = 1037   # pseudo stat: Energy Charge Efficiency from EffectType 37 (x (1 + value) on energy gained)
STAT_NAMES[CHARGE_EFF] = "Energy Charge Efficiency"
START_ENERGY = 1034   # pseudo stat: Energy restored at the start of battle (EffectType 34, e.g. Miraculous Anthem)
STAT_NAMES[START_ENERGY] = "Energy at battle start"


def stat_name(stat: int, is_pct: bool = False) -> str:
    n = STAT_NAMES.get(stat, f"stat {stat}")
    if stat in BASE_STATS:
        n = f"{n}%" if is_pct else f"{n} (flat)"
    return n


class StatBlock:
    """Additive stat sums. ATK/DEF/HP keep base, flat and pct separately; others live in `vals`."""

    def __init__(self):
        self._base: dict[int, float] = defaultdict(float)
        self.flat: dict[int, float] = defaultdict(float)
        self.pct: dict[int, float] = defaultdict(float)
        self.vals: dict[int, float] = defaultdict(float)

    def set_base(self, stat: int, value: float) -> None:
        self._base[stat] = value

    def base(self, stat: int) -> float:
        return self._base[stat]

    def get(self, stat: int) -> float:
        return self.vals[stat]

    def add_stat(self, stat: int, value: float, is_pct: bool = False) -> None:
        if stat in BASE_STATS:
            (self.pct if is_pct else self.flat)[stat] += value
        else:
            self.vals[stat] += value

    def final(self, stat: int) -> float:
        return (self._base[stat] + self.flat[stat]) * (1 + self.pct[stat])

    def add(self, other: "StatBlock") -> "StatBlock":
        for mine, theirs in ((self._base, other._base), (self.flat, other.flat),
                             (self.pct, other.pct), (self.vals, other.vals)):
            for k, v in theirs.items():
                mine[k] += v
        return self

    def copy(self) -> "StatBlock":
        s = StatBlock.__new__(StatBlock)   # the simulator copies a block per hit
        s._base = defaultdict(float, self._base)
        s.flat = defaultdict(float, self.flat)
        s.pct = defaultdict(float, self.pct)
        s.vals = defaultdict(float, self.vals)
        return s
