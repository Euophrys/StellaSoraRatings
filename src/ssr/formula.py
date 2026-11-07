"""Damage formula (AutumnVN's decompiled gist, docs/reference/damage-formula/)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .game import Hit, hit_pct
from .stats import (StatBlock, CRIT_RATE, CRIT_DMG, ELEM_DMG_BASE, ELEM_PEN_BASE, ELEM_IGNORE_RES_BASE,
                    ELEM_TAKEN_BASE, SLOT_OF_DAMAGE_TYPE, SLOT_DMG, SLOT_CRIT_RATE, SLOT_CRIT_DMG, SLOT_TAKEN,
                    DMG, DMG_DEALT, DMG_MULT, FINAL_DMG, FINAL_DMG2, DMG_TAKEN, DMG_TAKEN2, VUL, elem_stat)

# From 4.config.json: (value_lower, value_upper, amend_lower, amend_upper) per band.
RES_CURVE = {
    "low": (0.0, 250.0, 0.0, 0.25),
    "middle": (251.0, 750.0, 0.35, 0.6),
    "high": (751.0, 2000.0, 0.9, 0.99),
}
BASE_SUPPRESS = 0.1
DYNAMIC_SUPPRESS = 0.9


def def_amend(defense: float) -> float:
    defense = max(0.0, defense)
    return 1 - defense * 40 / (defense * 32 + 24000)


def er_amend(res: float, pen: float, vul: float = 0.0, ignore: float = 0.0) -> float:
    """Elemental RES damage multiplier."""
    eff = res * (1 - ignore) - pen
    if eff <= 0:
        return (1 + vul * BASE_SUPPRESS) + vul * eff * -0.01 * DYNAMIC_SUPPRESS
    band = "low" if eff <= 250 else "middle" if eff <= 750 else "high"
    vlo, vhi, alo, ahi = RES_CURVE[band]
    x = min(1.0, max(0.0, (eff - vlo) / (vhi - vlo)))
    return 1 - (alo + (ahi - alo) * x * x)


@dataclass
class Enemy:
    res: float = 250.0
    defense: float = 500.0
    broken: float = 1.0
    vul: float = 0.0
    taken: StatBlock = field(default_factory=StatBlock)
    res_by_element: dict = field(default_factory=dict)   # element (EET) -> RES, overriding `res` (non-weak elements)
    name: str = "generic"           # enemy preset (specs/enemies/<name>.yaml)
    resilience: float = 0.0         # resilience bar; 0 = no bar (never broken except via `broken`)
    break_time: float = 10.0        # seconds broken per break
    break_ratio: float = 1.5        # damage x while broken (unverified)
    lock_delay: float = 1.3         # GUESS: seconds from refill to the resilience lock
    lock_time: float = 4.7          # GUESS: seconds the bar can't be lowered
    ability: tuple = ()             # the boss's ability, as Modifiers
    fight_length: float | None = None


def slot_of(h: Hit) -> str:
    return SLOT_OF_DAMAGE_TYPE.get(h.damage_type, "other")


def hit_damage(h: Hit, skill_level: int, attacker: StatBlock, enemy: Enemy, intensity: float = 1.0) -> float:
    slot = slot_of(h)
    base = attacker.final(h.base_stat) * hit_pct(h, skill_level) * intensity * (1 + attacker.get(DMG_MULT))
    slot_dmg = 1 + (attacker.get(SLOT_DMG[slot]) if slot in SLOT_DMG else 0.0)
    elem_dmg = 1 + attacker.get(elem_stat(ELEM_DMG_BASE, h.element)) if h.element else 1.0
    general = 1 + attacker.get(DMG) + attacker.get(DMG_DEALT)
    p = min(1.0, max(0.0, attacker.get(CRIT_RATE) + (attacker.get(SLOT_CRIT_RATE[slot]) if slot in SLOT_CRIT_RATE else 0.0)))
    cd = attacker.get(CRIT_DMG) + (attacker.get(SLOT_CRIT_DMG[slot]) if slot in SLOT_CRIT_DMG else 0.0)
    crit = (1 - p) + p * cd
    if h.element:
        pen = attacker.get(elem_stat(ELEM_PEN_BASE, h.element))
        ign = attacker.get(elem_stat(ELEM_IGNORE_RES_BASE, h.element))
        er = er_amend(enemy.res_by_element.get(h.element, enemy.res), pen, enemy.vul + attacker.get(VUL), ign)
        elem_taken = 1 + enemy.taken.get(elem_stat(ELEM_TAKEN_BASE, h.element))
    else:
        er, elem_taken = 1.0, 1.0
    slot_taken = 1 + (enemy.taken.get(SLOT_TAKEN[slot]) if slot in SLOT_TAKEN else 0.0)
    general_taken = 1 + enemy.taken.get(DMG_TAKEN) + enemy.taken.get(DMG_TAKEN2)
    final = 1 + attacker.get(FINAL_DMG) + attacker.get(FINAL_DMG2)
    return (base * slot_dmg * elem_dmg * general * crit
            * er * def_amend(enemy.defense) * slot_taken * elem_taken * general_taken * enemy.broken * final)
