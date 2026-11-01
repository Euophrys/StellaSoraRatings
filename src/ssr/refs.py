"""Resolve potential/skill Param reference strings to values."""
from __future__ import annotations

from dataclasses import dataclass

from .data import GameData


@dataclass
class Ref:
    value: float | int | list | str
    is_enum: bool = False


def level_row(gd: GameData, table: str, base_id: int, level: int) -> dict:
    """Row for `base_id` at `level` (id + level*10), clamped to the highest level present."""
    t = gd.table(table)
    for lv in range(max(level, 1), 0, -1):
        row = t.get(str(base_id + lv * 10))
        if row is not None:
            return row
    raise KeyError(f"{table}: no level rows for {base_id}")


def _format(raw, fmt: list[str]) -> Ref:
    if fmt and fmt[0] == "Enum":
        return Ref(int(raw), True)
    if fmt and fmt[0] == "Text":
        return Ref(raw)
    v = float(raw)
    if fmt and fmt[0].startswith("10K"):
        v /= 10000.0
    return Ref(v)


def resolve(gd: GameData, ref: str, level: int) -> Ref:
    parts = ref.split(",")
    src = parts[0]
    if src == "HitDamage":
        return Ref([x * 1e-6 for x in gd.table("HitDamage")[parts[2]]["SkillPercentAmend"]])
    mode, base_id, field, fmt = parts[1], int(parts[2]), parts[3], parts[4:]
    if mode == "LevelUp":
        table = src if src.endswith("Value") else src + "Value"
        row = level_row(gd, table, base_id, level)
    else:
        row = gd.table(src)[str(base_id)]
    if fmt and fmt[0] == "Text":
        return Ref(gd.text(row[field]) or "")
    return _format(row.get(field, 0), fmt)
