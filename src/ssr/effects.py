"""Turn game effects (potentials, discs, buffs) into Modifiers.

Values always come from data. Semantics that the data doesn't encode (the
trigger behind a script-applied buff, which hits an attribute applies to) are
marked `assumed` / `needs_scope` so the kit YAML can pin them down.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from functools import lru_cache

from .data import GameData
from .refs import level_row
from .stats import (BASE_STATS, ELEM_TAKEN_BASE, DMG_TAKEN, DMG_TAKEN2, SLOT_TAKEN, stat_name)

STAT_EFFECT_TYPES = (12, 52)
APPLY_BUFF = 6
TAKEN_STATS = set(range(ELEM_TAKEN_BASE, ELEM_TAKEN_BASE + 6)) | {DMG_TAKEN, DMG_TAKEN2} | set(SLOT_TAKEN.values())


@dataclass(frozen=True)
class Trigger:
    event: str
    duration: float
    max_stacks: int = 1
    uptime: float | None = None
    icd: float = 0.0


@dataclass(frozen=True)
class Modifier:
    stat: int
    value: float
    is_pct: bool = False
    target: str = "self"            # self | team | enemy
    hit_tags: tuple[str, ...] = ()  # empty = all of the target's hits
    trigger: Trigger | None = None  # None = always on
    assumed: bool = False
    needs_scope: bool = False       # attribute only applies to some hits; kit should set hit_tags
    source: str = ""

    def label(self) -> str:
        return stat_name(self.stat, self.is_pct)

    def with_(self, **kw) -> "Modifier":
        return replace(self, **kw)


def _is_pct(stat: int, second_subtype: int | None) -> bool:
    # ATK/DEF/HP: EffectDesc Type2ID 1 = base, 2 = %, 3 = flat. Base and flat are both additive here.
    return stat in BASE_STATS and second_subtype == 2


def _target_for(stat: int, target1: int | None) -> str:
    if stat in TAKEN_STATS or target1 == 2:
        return "enemy"
    return "self"


@lru_cache(maxsize=None)
def _buff_index(gd: GameData) -> dict[int, dict]:
    """effect id -> the BuffValue row whose Effects list contains it."""
    idx: dict[int, dict] = {}
    for row in gd.table("BuffValue").values():
        for eid in row.get("Effects", []) or []:
            idx.setdefault(eid, row)
    return idx


def _buff_trigger(buff: dict, event: str = "unknown") -> Trigger:
    t = buff.get("Time", 0)
    duration = math.inf if t < 0 else t / 10000   # Time -1 = permanent
    return Trigger(event=event, duration=duration, max_stacks=max(1, buff.get("LaminatedNum", 1)))


def _interpret(gd: GameData, effect_row: dict | None, value_row: dict, source: str, notes: list[str],
               trigger: Trigger | None, target1: int | None, depth: int = 0) -> list[Modifier]:
    et = value_row.get("EffectType")
    if et in STAT_EFFECT_TYPES:
        stat = value_row.get("EffectTypeFirstSubtype")
        try:
            v = float(value_row.get("EffectTypeParam1", 0))
        except (TypeError, ValueError):
            notes.append(f"{source}: effect {value_row['Id']} has non-numeric value")
            return []
        m = Modifier(stat=stat, value=v, is_pct=_is_pct(stat, value_row.get("EffectTypeSecondSubtype")),
                     target=_target_for(stat, target1), trigger=trigger,
                     assumed=trigger is not None and trigger.uptime is None and trigger.event == "unknown",
                     source=source)
        return [m]
    if et == APPLY_BUFF and depth < 3:
        try:
            bid = int(value_row.get("EffectTypeParam1"))
        except (TypeError, ValueError):
            bid = None
        buff = gd.table("BuffValue").get(str(bid)) if bid else None
        if buff is None:
            notes.append(f"{source}: buff {bid} not found")
            return []
        trig = _buff_trigger(buff)
        tgt = (effect_row or {}).get("Target1", target1)
        out: list[Modifier] = []
        for eid in buff.get("Effects", []) or []:
            vrow = gd.table("EffectValue").get(str(eid))
            if vrow is None:
                notes.append(f"{source}: buff effect {eid} has no value row")
                continue
            out += _interpret(gd, gd.table("Effect").get(str(eid)), vrow, source, notes, trig, tgt, depth + 1)
        if not out:
            notes.append(f"{source}: buff {bid} has no damage effect")
        return out
    notes.append(f"{source}: EffectType {et} (effect {value_row.get('Id')}) has no damage model")
    return []


def effect_modifiers(gd: GameData, effect_id: int, source: str, notes: list[str] | None = None) -> list[Modifier]:
    """Interpret one un-leveled effect id (disc skills, base skills)."""
    notes = [] if notes is None else notes
    erow = gd.table("Effect").get(str(effect_id))
    vrow = gd.table("EffectValue").get(str(effect_id))
    if vrow is None:
        notes.append(f"{source}: effect {effect_id} has no value row")
        return []
    trig = None
    if erow is not None and erow.get("Trigger", 1) != 1 and vrow.get("EffectType") != APPLY_BUFF:
        trig = Trigger(event="unknown", duration=0.0)
    return _interpret(gd, erow, vrow, source, notes, trig, (erow or {}).get("Target1"))


def _oaa_row_modifiers(row: dict, source: str) -> list[Modifier]:
    out = []
    for i in (1, 2):
        stat = row.get(f"AttributeType{i}")
        if not stat:
            continue
        out.append(Modifier(stat=stat, value=row.get(f"Value{i}", 0) / 10000,
                            is_pct=stat in BASE_STATS and row.get(f"ParameterType{i}") == 2,
                            target=_target_for(stat, None), needs_scope=True, source=source))
    return out


def once_attr_modifiers(gd: GameData, oaa_id: int, source: str) -> list[Modifier]:
    row = gd.table("OnceAdditionalAttributeValue").get(str(oaa_id))
    return _oaa_row_modifiers(row, source) if row else []


def _potential_refs(p: dict) -> list[list[str]]:
    return [p[f"Param{i}"].split(",") for i in range(1, 16) if p.get(f"Param{i}")]


def potential_modifiers(gd: GameData, potential_id: int, level: int) -> tuple[list[Modifier], list[str]]:
    p = gd.table("Potential")[str(potential_id)]
    src = f"{gd.item_name(potential_id)} ({potential_id})"
    notes: list[str] = []
    mods: list[Modifier] = []
    direct = {p[f"EffectId{i}"] for i in range(1, 8) if p.get(f"EffectId{i}")}
    effects: dict[int, dict] = {}   # base id -> value row
    oaas: dict[int, dict] = {}
    for parts in _potential_refs(p):
        kind = parts[0]
        if kind in ("Effect", "EffectValue"):
            bid = int(parts[2])
            if bid in effects:
                continue
            if kind == "Effect":
                try:
                    effects[bid] = level_row(gd, "EffectValue", bid, level)
                except KeyError:
                    notes.append(f"{src}: effect row {bid} missing from data")
            elif str(bid) in gd.table("EffectValue"):
                effects[bid] = gd.table("EffectValue")[str(bid)]
        elif kind in ("OnceAdditionalAttribute", "OnceAdditionalAttributeValue"):
            bid = int(parts[2])
            if bid in oaas:
                continue
            try:
                oaas[bid] = (level_row(gd, "OnceAdditionalAttributeValue", bid, level)
                             if kind == "OnceAdditionalAttribute" else gd.table("OnceAdditionalAttributeValue")[str(bid)])
            except KeyError:
                notes.append(f"{src}: attribute row {bid} missing from data")
    for bid in direct - set(effects):
        try:
            effects[bid] = level_row(gd, "EffectValue", bid, level)
        except KeyError:
            if str(bid) in gd.table("EffectValue"):
                effects[bid] = gd.table("EffectValue")[str(bid)]
    bidx = _buff_index(gd)
    for bid, vrow in effects.items():
        erow = gd.table("Effect").get(str(bid))
        trig = None
        if vrow.get("EffectType") != APPLY_BUFF:
            if bid in bidx:
                trig = _buff_trigger(bidx[bid])
            elif bid not in direct:
                trig = Trigger(event="unknown", duration=0.0)
                notes.append(f"{src}: effect {bid} is applied by script (condition unknown)")
            elif erow is not None and erow.get("Trigger", 1) != 1:
                trig = Trigger(event="unknown", duration=0.0)
        mods += _interpret(gd, erow, vrow, src, notes, trig, (erow or {}).get("Target1"))
    for row in oaas.values():
        mods += _oaa_row_modifiers(row, src)
    if not mods and not notes:
        notes.append(f"{src}: no stat effect in data (behaviour only)")
    return mods, notes


def disc_modifiers(gd: GameData, disc_id: int, copies: int) -> tuple[list[Modifier], list[str]]:
    d = gd.table("Disc")[str(disc_id)]
    src = f"{gd.item_name(disc_id)} ({disc_id})"
    notes: list[str] = []
    mods: list[Modifier] = []
    lv = max(1, min(copies, 6))
    for row in gd.table("MainSkill").values():
        if row.get("GroupId") == d.get("MainSkillGroupId") and row.get("Level") == lv:
            for eid in row.get("EffectId", []):
                mods += effect_modifiers(gd, eid, src + " melody", notes)
    for g in ("SecondarySkillGroupId1", "SecondarySkillGroupId2"):
        gid = d.get(g)
        if not gid:
            continue
        for row in gd.table("SecondarySkill").values():
            if row.get("GroupId") == gid and row.get("Level") == 1:
                for eid in row.get("EffectId", []):
                    mods += effect_modifiers(gd, eid, src + " harmony", notes)
    return mods, notes
