"""Tick-based 120 s fight simulation producing total team damage."""
from __future__ import annotations

import bisect
import heapq
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from functools import lru_cache

from .data import GameData
from .effects import (MINION_STATS, Modifier, disc_modifiers, effect_modifiers, harmony_note_counts,
                      note_modifiers)
from .formula import Enemy, hit_damage, slot_of
from .game import toughness_adjust, char_base_stats, disc_base_stats, hit, hit_level, skill_cd, talent_nodes, ult_energy
from .kit import (ActionSpec, HitSpec, MinionSpec, ResolvedPotential, kit_buffs, passes_gates, resolve_buffs,
                  resolve_potential)
from .resilience import ExpectedICD, ResilienceBar
from .stats import ATK_SPD, CHARGE_EFF, DEF, ELEM_TAKEN_BASE, RES_BREAK_EFF, START_ENERGY, StatBlock
from .emblems import EmblemChargeEfficiency, EmblemPotentialLevel, line_relevant
from .team import FILLER, FILLER_SOURCE_DISC, Build, EmblemLine, EmblemSkillLevel, TeamConfig

_HIT_DAMAGE = hit_damage
DEFAULT_BUSY = 1.5   # GUESS: seconds after a main cast before another cast can start (animation)


@dataclass
class SimResult:
    total: float
    by_member: dict[int, float]
    by_slot: dict[tuple[int, str], float]
    casts: dict[tuple[int, str], int]
    first_cast: dict[tuple[int, str], float]
    unknown_modifiers: list[str]
    on_field_time: dict[int, float] = field(default_factory=dict)
    status_time: dict[str, float] = field(default_factory=dict)
    breaks: list[float] = field(default_factory=list)              # break start times
    broken_time: float = 0.0                                       # seconds broken within the fight
    resilience_by_member: dict[int, float] = field(default_factory=dict)   # resilience damage dealt (bar on or off)


# ---------------------------------------------------------------- caches

_POT_CACHE: dict = {}
_DISC_CACHE: dict = {}


def _potential(gd, kit, pid, lv) -> ResolvedPotential:
    key = (id(gd), kit.char_id, kit.role, pid, lv)
    if key not in _POT_CACHE:
        _POT_CACHE[key] = resolve_potential(gd, kit, pid, lv)
    return _POT_CACHE[key]


def _disc_stats(gd, disc_id, copies, level: int = 90) -> StatBlock:
    key = ("stats", id(gd), disc_id, copies, level)
    if key not in _DISC_CACHE:
        _DISC_CACHE[key] = disc_base_stats(gd, FILLER_SOURCE_DISC, level=level, copies=6) if disc_id == FILLER \
            else disc_base_stats(gd, disc_id, level=level, copies=copies)
    return _DISC_CACHE[key]


def _disc_mods(gd, disc_id, copies) -> list[Modifier]:
    """Disc melody/harmony modifiers; data-derived "self" effects are squad-wide per assumptions."""
    if disc_id == FILLER:
        return []
    key = ("mods", id(gd), disc_id, copies)
    if key not in _DISC_CACHE:
        _DISC_CACHE[key] = disc_modifiers(gd, disc_id, copies)[0]
    return _DISC_CACHE[key]


def _disc_element(gd, disc_id) -> int:
    """Disc element 1-6 (its effects only reach Trekkers of that element); 0 for neutral (EET 7) or filler."""
    if disc_id == FILLER:
        return 0
    el = gd.table("Disc")[str(disc_id)].get("EET", 0)
    return el if 1 <= el <= 6 else 0


DODGE_CD = 1.0   # user: seconds between dodges (the dodge cooldown)


# ---------------------------------------------------------------- helpers

@lru_cache(maxsize=None)
def _norm_event(ev: str, owner: int) -> str:
    """`self` / `main` -> member indices, in the event and in each `&while:` / `&recent:` suffix."""
    if "|" in ev:
        return "|".join(_norm_event(e, owner) for e in ev.split("|"))
    if "&" in ev:
        return "&".join(_norm_event(e, owner) for e in ev.split("&"))
    parts = ev.split(":")
    return ":".join([parts[0]] + [{"self": str(owner), "main": "0"}.get(p, p) for p in parts[1:]])


@lru_cache(maxsize=None)
def _event_matches(pattern: str, ev: str) -> bool:
    if "|" in pattern:
        return any(_event_matches(x, ev) for x in pattern.split("|"))
    pattern = pattern.split("&", 1)[0]   # "&recent:..." is checked by the simulator (needs hit history)
    p, e = pattern.split(":"), ev.split(":")
    if len(p) != len(e):
        return False
    return all(a == b or a == "any" for a, b in zip(p, e))


def _expand_who(ev: str, n: int, classes: list[int], elements: list[int] | None = None) -> str:
    """Who-tokens that depend on the team: `support` (members 1..n-1), `class<N>` (members of Character.Class N),
    `element<N>` (Trekkers of EET N), and intersections joined with `/` (`support/element6`: an Umbra support).
    E.g. `hit:class2:skill_dmg` = Skill DMG dealt by a Versatile Trekker. Expanded into `|` alternatives."""
    if "|" in ev:
        return "|".join(_expand_who(e, n, classes, elements) for e in ev.split("|"))
    base, amp, rest = ev.partition("&")
    parts = base.split(":")
    if len(parts) < 2:
        return ev

    def members_of(tok: str):
        if tok == "support":
            return set(range(1, n))
        if tok.startswith("class") and tok[5:].isdigit():
            return {i for i, c in enumerate(classes) if c == int(tok[5:])}
        if tok.startswith("element") and tok[7:].isdigit():
            return {i for i, e in enumerate(elements or []) if e == int(tok[7:])}
        return None
    sets = [members_of(tok) for tok in parts[1].split("/")]
    if any(x is None for x in sets):
        return ev
    idx = sorted(set.intersection(*sets))
    if not idx:
        return f"never:{parts[0]}"
    return "|".join(":".join([parts[0], str(i)] + parts[2:]) + amp + rest for i in idx)


def _targets(target: str, owner: int, n: int, classes: list[int] | None = None,
             elements: list[int] | None = None) -> list[int | str]:
    if "/" in target:   # intersection of groups, e.g. "class:2/element:5" = Lux Versatile Trekkers
        sets = [set(_targets(t, owner, n, classes, elements)) for t in target.split("/")]
        return sorted(set.intersection(*sets), key=str)
    if target == "support":
        return list(range(1, n))
    if target.startswith("class:"):
        want = int(target.split(":")[1])
        return [i for i, c in enumerate(classes or []) if c == want]
    if target.startswith("element:"):   # Trekkers of one element (EET), e.g. "element:6" = Umbra Trekkers
        want = int(target.split(":")[1])
        return [i for i, e in enumerate(elements or []) if e == want]
    if target == "team":
        return list(range(n))
    if target == "main":
        return [0]
    if target == "enemy":
        return ["enemy"]
    return [owner]


@dataclass
class _Mod:
    mod: Modifier
    owner: int
    receivers: list            # member indices or "enemy"
    event: str = ""            # normalized; "" = always on
    stacks: list = field(default_factory=list)   # expiry times
    last_trigger: float = -1e9
    count: int = 0
    constant: float = 1.0      # multiplier for always-on / uptime-based mods


@dataclass
class _Member:
    idx: int
    cfg: object
    kit: object
    actions: dict[str, ActionSpec]
    skill_levels: dict[str, int]
    pot_levels: dict[int, int]
    mark_tags: set
    extra_casts: dict
    reset_cd: dict
    cd_reduce: list
    procs: list
    cd_when: list = field(default_factory=list)   # (action, scale, condition): see cooldown() in simulate
    static: StatBlock = None
    minion_static: StatBlock = None   # what the member's minions get: stat sheet + buffs that reach minions
    cd_ready: dict = field(default_factory=dict)
    cd: dict = field(default_factory=dict)
    energy: float = 0.0
    ult_cost: float = 0.0
    energy_cap: dict = field(default_factory=dict)
    charge: float = 1.0   # Charge Efficiency emblem multiplier on energy gained
    max_charges: dict = field(default_factory=dict)    # action -> stored uses (only actions with > 1)
    charges: dict = field(default_factory=dict)        # action -> uses ready now
    recharge: dict = field(default_factory=dict)       # action -> completion times of charges recharging
    use_interval: dict = field(default_factory=dict)   # action -> min seconds between stored uses
    last_use: dict = field(default_factory=dict)
    cast_count: dict = field(default_factory=lambda: defaultdict(int))
    minions: dict = field(default_factory=dict)        # pool name -> MinionSpec (potential rules applied)
    resources: dict = field(default_factory=dict)      # resource name -> amount held now
    res_max: dict = field(default_factory=dict)        # resource name -> most that can be held


def simulate(gd: GameData, team: TeamConfig, build: Build, emblems: bool = True,
             discs: tuple[list, list] | None = None, extra: list | None = None) -> SimResult:
    """Simulate one fight.

    discs: (main_slots, support_slots) as [(disc_id, copies)], default the team's lineup.
    extra: [(member_idx, Modifier | EmblemLine | EmblemSkillLevel | EmblemPotentialLevel | EmblemChargeEfficiency
            | ResolvedPotential)] for rating.
    """
    extra = extra or []
    discs_main, discs_support = discs if discs is not None else (team.discs_main, team.discs_support)
    disc_team = team.assumptions.get("disc_stats_target", "team") == "team"
    chars = gd.table("Character")
    sink = _ModSink(team, classes=[chars[str(m.char_id)].get("Class", 0) for m in team.members],
                    elements=[chars[str(m.char_id)].get("EET", 0) for m in team.members])

    members = [_setup_member(gd, team, build, i, emblems, extra, sink) for i in range(len(team.members))]
    _add_squad_mods(gd, team, discs_main, disc_team, sink)
    _static_sheets(gd, team, members, list(discs_main) + list(discs_support), disc_team, emblems, extra)

    all_reach = team.assumptions.get("minion_buffs", "text") == "all"
    enemy_static = team.enemy.taken.copy()
    dynamic = _fold_constants(sink.mods, members, enemy_static, all_reach)
    for m in members:   # "at the start of battle, ... restore N Energy" (always-on, folded into the sheet)
        m.energy = m.static.get(START_ENERGY)
    for md in sink.mods:
        if md.mod.needs_scope and not md.mod.hit_tags:
            sink.unknown.add(f"{md.mod.source}: {md.mod.label()} applied to all hits (scope unknown)")

    fight = _Fight(gd, team, members, sink, dynamic, enemy_static, all_reach)
    fight.set_dodges(extra)
    fight.run()
    return fight.result()


# ---------------------------------------------------------------- setup: modifiers

class _ModSink:
    """Collects the fight's modifiers: who each one reaches, and whether it's always on, averaged or event-driven."""

    def __init__(self, team: TeamConfig, classes: list[int], elements: list[int]):
        self.n = len(team.members)
        self.classes = classes
        self.elements = elements
        self.uptime_default = float(team.assumptions.get("unknown_trigger_uptime", 1.0))
        self.mods: list[_Mod] = []
        self.unknown: set[str] = set()

    def event(self, ev: str, owner: int) -> str:
        """An event pattern with its team-dependent who-tokens expanded and self/main resolved for `owner`."""
        return _norm_event(_expand_who(ev, self.n, self.classes, self.elements), owner)

    def add(self, m: Modifier, owner: int, src_target: str | None = None, element: int = 0):
        elements = self.elements
        if m.main_element and elements[0] != m.main_element:
            return   # "the main <Element> Trekker": the main isn't that element
        rec = _targets(src_target or m.target, owner, self.n, self.classes, elements)
        if element:   # element-locked disc: only that element's Trekkers (or the enemy, if any are in the team)
            if element not in elements:
                return
            rec = [r for r in rec if r == "enemy" or elements[r] == element]
            if not rec:
                return
        t = m.trigger
        if t is None:
            self.mods.append(_Mod(m, owner, rec))
        elif t.uptime is not None or t.event == "unknown":
            up = t.uptime if t.uptime is not None else self.uptime_default
            if t.uptime is None:
                self.unknown.add(f"{m.source}: {m.label()} (uptime {up:g} x {t.max_stacks} stacks assumed)")
            self.mods.append(_Mod(m, owner, rec, constant=up * t.max_stacks))
        else:
            self.mods.append(_Mod(m, owner, rec, event=self.event(t.event, owner)))


def _add_squad_mods(gd: GameData, team: TeamConfig, discs_main, disc_team: bool, sink: _ModSink):
    """Main-slot disc effects, harmony notes and the boss's own ability."""
    for d, c in discs_main:
        el = _disc_element(gd, d)
        for md in _disc_mods(gd, d, c):
            sink.add(md, 0, "team" if (disc_team and md.target == "self") else None, el)
    notes_lv = int(team.assumptions.get("harmony_notes", 1))   # notes for main-disc harmonies at this level
    if notes_lv > 0:
        counts = harmony_note_counts(gd, [d for d, _ in discs_main if d != FILLER], notes_lv)
        for md in note_modifiers(gd, counts):
            sink.add(md, 0, "team" if disc_team else None)
    for md in team.enemy.ability:   # the boss's ability (enemy preset)
        sink.add(md, 0)


def _reaches_minions(mod: Modifier, all_reach: bool) -> bool:
    return all_reach or bool(mod.minions) or mod.stat in MINION_STATS


def _const_reaches_minions(mod: Modifier, all_reach: bool) -> bool:
    """Minions summon with a snapshot of the summoner's sheet at battle start (user, in-game), so truly
    always-on buffs (no trigger) reach them whatever their wording. Buffs that come and go, including those
    averaged as `uptime x stacks`, reach minions only if they name minions / friendly units."""
    return mod.trigger is None or _reaches_minions(mod, all_reach)


def _fold_constants(mods: list[_Mod], members: list[_Member], enemy_static: StatBlock, all_reach: bool) -> list[_Mod]:
    """Fold unscoped always-on mods into the static sheets; returns the rest (scoped, event-driven or `while:`)."""
    dynamic: list[_Mod] = []
    for md in mods:
        if md.event == "" and not md.mod.hit_tags:
            for r in md.receivers:
                blks = [enemy_static] if r == "enemy" else (
                    [members[r].static] + ([members[r].minion_static] if _const_reaches_minions(md.mod, all_reach)
                                           else []))
                for blk in blks:
                    blk.add_stat(md.mod.stat, md.mod.value * md.constant, md.mod.is_pct)
        else:
            dynamic.append(md)
    return dynamic


# ---------------------------------------------------------------- setup: members

def _setup_member(gd: GameData, team: TeamConfig, build: Build, i: int, emblems: bool, extra: list,
                  sink: _ModSink) -> _Member:
    """One member's levels, potentials, actions, cooldowns and minions; adds their modifiers to `sink`."""
    mc = team.members[i]
    kit = mc.kit
    lines = (list(mc.emblems) if emblems else []) + [x for (j, x) in extra if j == i]
    levels = dict(mc.skill_levels)
    for x in lines:
        if isinstance(x, EmblemSkillLevel) and x.applies_to(mc.role):
            levels[x.action] = levels.get(x.action, 10) + x.plus
    pot_levels = {p: 1 for p in mc.pinks}
    pot_levels.update(build.levels_for(mc.char_id))
    for x in lines:   # Lv90 "+N": fights at target + N (cap 9); not taken still fights at N
        if isinstance(x, EmblemPotentialLevel) and line_relevant(x, 0, mc.role):
            pot_levels[x.potential_id] = min(9, pot_levels.get(x.potential_id, 0) + x.plus)
    resolved = [_potential(gd, kit, p, lv) for p, lv in pot_levels.items()]
    rated = [x for x in lines if isinstance(x, ResolvedPotential)]
    resolved += rated
    owned = set(pot_levels) | {rp.potential_id for rp in rated}
    # A potential that `excludes` another in the build does nothing (it still counts as owned for hits'
    # requires/excludes, and for its level).
    resolved = [rp for rp in resolved if not owned & set(rp.excludes)]

    def keep(h: HitSpec) -> bool:
        if h.squad and sum(e == h.squad[0] for e in sink.elements) < h.squad[1]:
            return False
        return passes_gates(h, owned)

    actions = _member_actions(kit, resolved, keep)
    if kit.ult_only_with and not set(kit.ult_only_with) & {x.char_id for x in team.members}:
        actions.pop("ult", None)
    m = _Member(
        idx=i, cfg=mc, kit=kit, actions=actions, skill_levels=levels, pot_levels=pot_levels,
        mark_tags={t for rp in resolved for t in rp.mark_tags},
        extra_casts={k: v for rp in resolved for k, v in rp.extra_casts.items()},
        reset_cd={**kit.reset_cd, **{k: v for rp in resolved for k, v in rp.reset_cd.items()}},
        cd_reduce=[rp.cd_reduce for rp in resolved if rp.cd_reduce],
        cd_when=[(c["action"], float(c["scale"]), _norm_event(c["when"], i)) for rp in resolved for c in rp.cd_when],
        procs=[(sink.event(p.event, i),
                replace(p, when=_norm_event(p.when, i), gain=tuple((r, float(v)) for r, v in p.gain),
                        cost=tuple((r, float(v)) for r, v in p.cost)) if (p.when or p.gain or p.cost) else p)
               for p in [*kit.procs, *(p for rp in resolved for p in rp.procs)] if keep(p)],
    )
    m.res_max = dict(kit.resources)
    m.resources = {r: 0.0 for r in kit.resources}
    _check_procs(gd, m)
    _setup_cooldowns(gd, m, resolved)
    m.minions = {pool: _minion_pool(ms, resolved, keep, i, sink) for pool, ms in kit.minions.items()}
    if "ult" in actions and actions["ult"].skill_id:
        m.ult_cost = ult_energy(gd, actions["ult"].skill_id)
        for rp in resolved:
            m.ult_cost *= rp.ult_cost_scale
    m.charge = 1.0 + sum(x.value for x in lines if isinstance(x, EmblemChargeEfficiency) and x.role == mc.role)
    _add_member_mods(gd, m, resolved, owned, lines, sink)
    return m


def _member_actions(kit, resolved: list[ResolvedPotential], keep) -> dict[str, ActionSpec]:
    """The kit's actions with the potentials' added actions and added / replaced hits, gated hits dropped."""
    actions: dict[str, ActionSpec] = {}
    for name, a in kit.actions.items():
        actions[name] = replace(a, hits=list(a.hits))
    for rp in resolved:
        for name, a in rp.add_actions.items():
            actions[name] = replace(a, hits=list(a.hits))
    for rp in resolved:
        for name, hs in rp.replace_hits.items():
            if name in actions:
                actions[name].hits = list(hs)
    for rp in resolved:
        for name, hs in rp.add_hits.items():
            if name in actions:
                actions[name].hits += list(hs)
    for a in actions.values():
        a.hits = [h for h in a.hits if keep(h)]
    return actions


def _check_procs(gd: GameData, m: _Member):
    """Proc combinations the simulator doesn't model are an error, not a silent guess."""
    who = gd.char_name(m.cfg.char_id)
    for _, p in m.procs:
        if p.chance < 1 and p.restart:
            raise ValueError(f"{who}: proc {p.hit_id} on {p.event!r}: `chance` with `restart` "
                             "isn't supported (an expected-value refreshed DoT isn't modelled)")
        if p.chance < 1 and (p.cost or p.summon):
            raise ValueError(f"{who}: proc {p.hit_id} on {p.event!r}: `chance` with `cost` "
                             "or `summon` isn't supported (an expected-value spend or summon isn't modelled)")
        for r, _ in (*p.gain, *p.cost):
            if r not in m.kit.resources:
                raise ValueError(f"{who}: proc {p.hit_id} uses resource {r!r}, "
                                 "which the kit section's `resources:` doesn't declare")


def _setup_cooldowns(gd: GameData, m: _Member, resolved: list[ResolvedPotential]):
    """Cooldowns, energy caps and stored charges from the Skill table, scaled by the potentials."""
    for name, a in m.actions.items():
        if a.skill_id:
            m.cd[name] = skill_cd(gd, a.skill_id)
            sk = gd.table("Skill").get(str(a.skill_id), {})
            if sk.get("GetEnergyLimit"):
                m.energy_cap[name] = sk["GetEnergyLimit"] / 10000
            n_ch = (a.charges or sk.get("SectionAmount", 1) or 1) + sum(rp.add_charges.get(name, 0) for rp in resolved)
            if n_ch > 1:
                m.max_charges[name] = n_ch
                m.charges[name] = n_ch
                m.recharge[name] = []
                m.use_interval[name] = a.use_interval if a.use_interval is not None \
                    else sk.get("UseInterval", 0) / 10000
                m.last_use[name] = -1e9
        for rp in resolved:
            if name in rp.cd_scale and name in m.cd:
                m.cd[name] *= rp.cd_scale[name]


def _minion_pool(ms: MinionSpec, resolved: list[ResolvedPotential], keep, i: int, sink: _ModSink) -> MinionSpec:
    """A minion pool with the potentials' rules applied and its events resolved for member `i`."""
    rules, adds, reacts = {}, defaultdict(float), list(ms.reactions)
    for rp in resolved:
        for k, v in rp.minion_rules.get(ms.name, {}).items():
            if k.endswith("_add"):   # additive, e.g. duration_add: +3 s of lifetime
                adds[k[:-4]] += float(v)
            elif k == "reactions":   # several potentials can each add reactions
                reacts += v
            else:
                rules[k] = v
    ms = replace(ms, **rules, reactions=reacts)
    ms = replace(ms, **{k: getattr(ms, k) + v for k, v in adds.items()})
    return replace(ms, summon=sink.event(ms.summon, i) if ms.summon else "",
                   sacrifice_on=sink.event(ms.sacrifice_on, i) if ms.sacrifice_on else "",
                   resummon_on=sink.event(ms.resummon_on, i) if ms.resummon_on else "",
                   attacks=[h for h in ms.attacks if keep(h)],
                   reactions=[replace(h, event=sink.event(h.event, i)) for h in ms.reactions if keep(h)])


def _add_member_mods(gd: GameData, m: _Member, resolved: list[ResolvedPotential], owned: set, lines: list,
                     sink: _ModSink):
    """Potentials, talent nodes, kit buffs and rated extras."""
    mc, kit, i = m.cfg, m.kit, m.idx
    for rp in resolved:
        for md in rp.modifiers:
            sink.add(md, i)
    talent_effects, talent_keys = talent_nodes(gd, mc.char_id, mc.talents)
    for eid in talent_effects:
        for md in effect_modifiers(gd, eid, f"{gd.char_name(mc.char_id)} talent node ({eid})"):
            sink.add(md, i)
    for tid in talent_keys:
        if tid not in kit.talents:
            sink.unknown.add(f"{gd.char_name(mc.char_id)} key talent {tid}: not in the kit spec, not modelled")
    for md in resolve_buffs(gd, kit, m.skill_levels, owned, kit_buffs(kit, talent_keys)):
        sink.add(md, i)
    for x in lines:
        if isinstance(x, Modifier):
            sink.add(x, i)


def _static_sheets(gd: GameData, team: TeamConfig, members: list[_Member], discs: list, disc_team: bool,
                   emblems: bool, extra: list):
    """Each member's sheet before buffs: base stats, disc stats, emblem stat lines and bonus stats."""
    disc_stats = StatBlock()
    for d, c in discs:
        disc_stats.add(_disc_stats(gd, d, c, team.disc_level))
    for i, m in enumerate(members):
        s = char_base_stats(gd, m.cfg.char_id, m.cfg.level)
        if disc_team or i == 0:
            s.add(disc_stats)
        lines = list(m.cfg.emblems) if emblems else []
        lines += [x for (j, x) in extra if j == i and isinstance(x, EmblemLine)]
        for e in lines:
            if isinstance(e, EmblemLine):
                s.add_stat(e.stat, e.value, e.is_pct)
        for stat, v, pct in m.cfg.bonus_stats:   # team-file flat extras (build-level stats)
            s.add_stat(stat, v, pct)
        m.static = s
        m.minion_static = s.copy()


# ---------------------------------------------------------------- the fight

class _Fight:
    """The fight timeline: buffs and statuses, events, casts, hits and minions, one tick at a time."""

    def __init__(self, gd: GameData, team: TeamConfig, members: list[_Member], sink: _ModSink,
                 dynamic: list[_Mod], enemy_static: StatBlock, all_reach: bool):
        n = len(members)
        self.gd, self.team, self.members, self.main, self.n = gd, team, members, members[0], n
        self.elements = sink.elements
        self.roles = [m.role for m in team.members]
        self.unknown = sink.unknown
        self.uptime_default = sink.uptime_default
        # A new stack of a buff resets every stack's timer (user, in game: Gerie's Delight in Ruin, 6 stacks all drop at
        # once; BuffValue TimeSuperposition 2 on nearly every buff). "independent" lets each stack expire on its own.
        self.refresh_stacks = team.assumptions.get("stack_timers", "refresh") == "refresh"
        self.all_reach = all_reach
        self.enemy_static = enemy_static
        self.dt, self.T = team.tick, team.fight_length

        # modifiers
        mods = sink.mods
        self.by_event: list[_Mod] = [md for md in dynamic if md.event and not md.event.startswith("while:")]
        self.while_mods: list[_Mod] = [md for md in dynamic if md.event.startswith("while:")]
        self.scoped_const: list[_Mod] = [md for md in dynamic if not md.event]
        # Status name -> every event-driven mod carrying it. Names are fight-wide: one status can come from several
        # buffs (Teresa's Surging Shield from her own skill and, with Restarting, from squadmates' casts) or from
        # several members (Chill on the enemy), and it holds the most stacks any of its sources gives.
        self.named: dict[str, list[_Mod]] = defaultdict(list)
        for md in self.by_event:
            if md.mod.name:
                self.named[md.mod.name].append(md)
        self.named = dict(self.named)
        self.norm = sink.event
        self.pools = {name for m in members for name in m.minions}
        self.status_parsed: dict = {}   # status expression -> ([(named mods, pool name or None)], least stacks)
        self.alt_parsed: dict = {}      # event pattern -> its parsed alternatives (event_alts)
        self.status_time: dict = defaultdict(float)
        # Enemy-side hit tags: an enemy modifier with `hit_tags: [by_support]` (or by_main, or a damage bucket such as
        # minion_dmg) only applies to hits by those members / of that bucket ("Skill DMG taken from Support Trekkers").
        # Added to the enemy lookup only when some enemy modifier asks, so other fights plan exactly as before.
        self.enemy_tags = any("enemy" in md.receivers and any(
            tg in ("by_main", "by_support") or tg.endswith("_dmg") for tg in md.mod.hit_tags) for md in mods)
        # Sheets can carry these too (team-file bonus_stats, emblem stat lines), not only modifiers.
        self.has_charge_mods = any(md.mod.stat == CHARGE_EFF for md in mods) or any(
            m.static.get(CHARGE_EFF) for m in members)
        self.has_atk_spd = any(md.mod.stat == ATK_SPD and 0 in md.receivers for md in mods) or bool(
            members[0].static.get(ATK_SPD))
        self.emit_plans: dict = {}   # event -> what it can touch: emit is the hot path, and most events match very little
        self.stat_plans: dict = {}   # (receiver, minion, tags) -> (sheet with the constant mods folded in, by_event,
        #                              while, [last key, last sheet])

        # members on the field, casts, minions
        self.on_field_until = [0.0] * n
        self.on_field_time = [0.0] * n
        self.last_cast: dict = {}   # (member, action) -> time of its last cast
        self.first_cast: dict = {}
        self.alive: dict = defaultdict(list)   # (member, pool) -> [{"uid", "expire", "k", "ready"}] out, oldest first
        self.minion_uid = 0
        self.holds = {(int(h["member"]), h["action"]): (_norm_event(h["until"], int(h["member"])),
                                                         float(h.get("max_wait", math.inf)),
                                                         _norm_event(h["only_if"], int(h["member"]))
                                                         if h.get("only_if") else "") for h in team.hold}
        self.hold_since: dict = {}

        # resilience bar
        en = team.enemy
        self.bar = (ResilienceBar(max=en.resilience, break_time=en.break_time, break_ratio=en.break_ratio,
                                  lock_delay=en.lock_delay, lock_time=en.lock_time)
                    if en.resilience > 0 and en.breaks else None)
        self.adjust = [toughness_adjust(gd, m.char_id) for m in team.members]
        self.resilience_by_member: dict = defaultdict(float)

        # hits and damage
        self.by_slot: dict = defaultdict(float)
        self.by_member: dict = defaultdict(float)
        self.queue: list = []   # (time, seq, member, HitSpec, action_name, cast_id)
        self.seq = 0
        self.hit_cache: dict = {}
        self.last_hit: dict = {}   # (member, tag) -> time of that member's last hit with the tag
        self.energy_used: dict = defaultdict(float)
        self.dmg_memo: dict = {}   # (hit id, level) -> (attacker sheet, enemy sheet, damage before the hit's own mult)
        self.mark_up: dict = defaultdict(bool)      # element -> a Mark of that element is on the enemy
        self.next_mark: dict = defaultdict(float)   # element -> mark ICD end

        # procs and followups
        self.restart_gen: dict = defaultdict(int)   # proc / minion-schedule key -> current generation
        self.proc_ready: dict = defaultdict(float)
        self.proc_expected: dict = {}   # (member, proc) -> ExpectedICD for chance procs
        self.proc_count: dict = defaultdict(int)
        self.followup_count: dict = defaultdict(int)
        self.main_event_followups = [(name, sink.event(a.followup.event, 0), a.followup.every)
                                     for name, a in self.main.actions.items() if a.followup and a.followup.event]

        # the main's own timeline
        self.busy_until = 1.0      # main can't start a cast before this
        self.lock_until = 1.0      # main can't auto before this
        self.pending: list = []    # (ready_time, action_name) for main followups / extra casts
        self.cancel_dodges: list = []   # times of the dodges that cancel an action into its followup, sorted
        self.once_used: dict = defaultdict(set)   # (kind, owner, id) -> its "&once" event alternatives already used
        self.auto_clock = 0.0
        self.auto_loop = 0
        for m in members:
            for name in m.actions:
                m.cd_ready[name] = 0.0
        self.main.cd_ready["skill"] = 1.0
        self._setup_autos()

    # ---------------------------------------------------------------- statuses and conditions

    def status_stacks(self, name: str, t: float) -> int:
        """Stacks of a status; "a+b" sums several statuses, "a>=N" is 0 below N stacks.
        A minion pool's name counts its minions out."""
        parsed = self.status_parsed.get(name)
        if parsed is None:
            names, _, least = name.partition(">=")
            parsed = self.status_parsed[name] = (
                [(self.named.get(nm, ()), nm if nm in self.pools else None) for nm in names.split("+")],
                int(least or 1))
        k = 0
        for mds, pool in parsed[0]:
            if mds:
                k += max(sum(1 for x in md.stacks if x > t) if md.stacks else 0 for md in mds)
            if pool is not None:
                k += sum(len(v) for (mi, p), v in self.alive.items() if p == pool)
        return k if k >= parsed[1] else 0

    def who(self, tok: str) -> range | tuple:
        """Members a condition's <who> names: an index, `any` or `support` (any of them counts)."""
        if tok == "any":
            return range(self.n)
        if tok == "support":
            return range(1, self.n)
        return (int(tok),)

    def condition(self, ev: str, t: float) -> int:
        """Multiplier for a "while:" modifier at time t (0 = inactive)."""
        if "&" in ev:   # while:A&while:B: the first condition's stacks, while all the others hold
            first, *rest = ev.split("&")
            return self.condition(first, t) if all(self.condition(c, t) for c in rest) else 0
        parts = ev.split(":")   # while:on_field:<who> | while:status:<name>
        kind = parts[1]
        members = self.members
        if kind == "not":   # while:not:<condition>: active exactly when the condition isn't
            return int(not self.condition("while:" + ":".join(parts[2:]), t))
        if kind == "status":
            return self.status_stacks(parts[2], t)
        if kind == "resource":   # while:resource:<member>:<name>>=N (or >N): that member holds that much
            name, op, want = re.split("(>=?)", parts[3])
            for mi in self.who(parts[2]):
                have = members[mi].resources.get(name, 0.0)
                if have >= float(want) - 1e-9 if op == ">=" else have > float(want) + 1e-9:
                    return 1
            return 0
        if kind == "cd_within":   # while:cd_within:<member>:<action>:<seconds>: cooldown left <= N s
            return int(any(members[mi].cd_ready.get(parts[3], 0.0) - t <= float(parts[4]) + 1e-9
                           for mi in self.who(parts[2])))
        if kind == "in_action":   # while:in_action:<member>:<action>: within that action's lock after its last cast
            act = parts[3]
            for mi in self.who(parts[2]):
                last = self.last_cast.get((mi, act))
                a = members[mi].actions.get(act)
                if last is not None and a is not None and t - last <= a.lock + 1e-9:
                    return 1
            return 0
        if kind == "cast_within":   # while:cast_within:<who>:<action>:<seconds>: cast that recently
            for mi in self.who(parts[2]):
                last = self.last_cast.get((mi, parts[3]))
                if last is not None and t - last <= float(parts[4]) + 1e-9:
                    return 1
            return 0
        if kind == "broken":   # while:broken: the enemy's resilience bar is broken
            if self.bar is None:   # no bar: today's behaviour, the unknown_trigger_uptime assumption (on if > 0)
                return int(self.team.enemy.breaks and self.uptime_default > 0)
            return int(self.bar.broken(t))
        if kind == "vul":   # while:vul:<element>: the enemy has that element's VUL (an <Element> DMG Taken debuff up)
            st = ELEM_TAKEN_BASE + int(parts[2]) - 1
            if self.enemy_static.get(st) > 0:
                return 1
            return int(any(md.mod.stat == st and md.mod.value > 0 and "enemy" in md.receivers
                           and (not md.event or any(x > t for x in md.stacks))
                           for md in self.by_event + self.scoped_const))
        if kind == "mark":   # while:mark:<element>: a Mark of that element is on the enemy
            return int(self.mark_up[int(parts[2])])
        if kind == "squad":   # while:squad:<element>:<n>: at least n Trekkers of that element (EET) in the squad
            return int(self.elements.count(int(parts[2])) >= int(parts[3]))
        if kind == "on_field":
            who = parts[2]
            idx = [i for i in range(self.n) if (who == "any" or (who == "support" and self.roles[i] == "support")
                                                 or who == str(i))]
            return any(self.on_field_until[i] > t for i in idx)
        return False

    def event_alts(self, pattern: str) -> list:
        """A pattern's `|` alternatives, each as (alt, base event, &once, [(recent tag, seconds)], [while conditions])."""
        parsed = self.alt_parsed.get(pattern)
        if parsed is None:
            parsed = []
            for alt in pattern.split("|"):
                base, *suffixes = alt.split("&")
                once, recents, whiles = False, [], []
                for s in suffixes:
                    if s == "once":
                        once = True
                    elif s.startswith("recent:"):
                        tag, _, secs = s[len("recent:"):].rpartition(":")
                        recents.append((tag, float(secs)))
                    elif s.startswith("while:"):
                        whiles.append(s)
                    else:
                        raise ValueError(f"event {pattern!r}: unknown suffix &{s} (have &once, &recent:, &while:)")
                parsed.append((alt, base, once, recents, whiles))
            self.alt_parsed[pattern] = parsed
        return parsed

    def passing_alt(self, pattern: str, ev: str, t: float, once_key) -> tuple | None:
        """The alternative of `pattern` that event `ev` counts for at t, as (alt, uses &once), or None. Per alternative:
        - `&recent:<tag>:<seconds>`: the member that emitted the event also landed a <tag> hit within the last
          <seconds> (e.g. a minion hit counts only if its summoner dealt Skill DMG recently);
        - `&while:<condition>`: only while the condition holds (`cast:self:skill&while:status:berserk`);
        - `&once`: only the first time it fires in the fight ("Triggers once every 5 minutes"). The caller marks it
          used once the trigger really fired (`use_once`); alternatives without it are tried first."""
        if "&" not in pattern:
            return (pattern, False) if _event_matches(pattern, ev) else None
        parts = ev.split(":")
        who = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        found = None
        for alt, base, once, recents, whiles in self.event_alts(pattern):
            if not _event_matches(base, ev) or (once and alt in self.once_used[once_key]):
                continue
            if not all((last := self.last_hit.get((who, tag))) is not None and t - last <= secs + 1e-9
                       for tag, secs in recents):
                continue
            if not all(self.condition(w, t) for w in whiles):
                continue
            if not once:
                return alt, False
            found = found or (alt, True)
        return found

    def use_once(self, once_key, alt: tuple):
        if alt[1]:
            self.once_used[once_key].add(alt[0])

    def event_ok(self, pattern: str, ev: str, t: float, once_key) -> bool:
        """Whether `ev` counts for `pattern` now, for triggers that always fire when it does (an `&once` is used)."""
        alt = self.passing_alt(pattern, ev, t, once_key)
        if alt:
            self.use_once(once_key, alt)
        return alt is not None

    # ---------------------------------------------------------------- events

    def emit_plan(self, ev: str) -> tuple:
        """What an event can touch: modifiers it triggers or resets, main followups, members' procs and minion pools."""
        def pool_listens(ms: MinionSpec) -> bool:
            return any(_event_matches(h.event, ev) for h in ms.reactions) or any(
                e and _event_matches(e, ev) for e in (ms.sacrifice_on, ms.resummon_on, ms.summon))

        plan_mods = []   # (mod, the event resets it, the event triggers it, it has &recent/&once/&while checks)
        for md in self.by_event:
            resets = any(_event_matches(self.norm(r, md.owner), ev) for r in md.mod.trigger.reset_on or ())
            matches = _event_matches(md.event, ev)
            if resets or matches:
                plan_mods.append((md, resets, matches, "&" in md.event))
        plan_followups = [f for f in self.main_event_followups if _event_matches(f[1], ev)]
        plan_members = []
        for m in self.members:
            procs = [(pev, p) for pev, p in m.procs if _event_matches(pev, ev)]
            pools = [(pool, ms) for pool, ms in m.minions.items() if pool_listens(ms)]
            if procs or pools:
                plan_members.append((m, procs, pools))
        plan = (plan_mods, plan_followups, plan_members) if (plan_mods or plan_followups or plan_members) else ()
        self.emit_plans[ev] = plan
        return plan

    def emit(self, ev: str, t: float):
        plan = self.emit_plans.get(ev)
        if plan is None:
            plan = self.emit_plan(ev)
        if not plan:
            return
        plan_mods, plan_followups, plan_members = plan
        for md, resets, matches, checked in plan_mods:
            if resets and md.stacks:
                md.stacks = []
            if not matches:
                continue
            if not checked:
                self.activate(md, t)
                continue
            key = ("mod", id(md))
            alt = self.passing_alt(md.event, ev, t, key)
            if alt and self.activate(md, t):
                self.use_once(key, alt)
        for fname, fev, every in plan_followups:
            if "&" in fev and not self.event_ok(fev, ev, t, ("followup", fname)):
                continue
            self.followup_count[fname] += 1
            if self.followup_count[fname] % every == 0:
                self.pending.append((max(t, self.lock_until), fname))
        for m, procs, pools in plan_members:
            for pev, p in procs:
                if "&" not in pev:
                    self.fire_proc(m, p, t)
                    continue
                key = ("proc", m.idx, p)
                alt = self.passing_alt(pev, ev, t, key)
                if alt and self.fire_proc(m, p, t):
                    self.use_once(key, alt)
            for pool, ms in pools:
                self.pool_event(m, pool, ms, ev, t)

    def activate(self, md: _Mod, t: float) -> bool:
        """An event-driven modifier's trigger matched: add its stacks (every-Nth, ICD and stacks_from permitting).
        Returns whether it activated."""
        trig = md.mod.trigger
        if trig.every > 1:
            md.count += 1
            if md.count % trig.every:
                return False
        if t - md.last_trigger < trig.icd - 1e-9:
            return False
        add = trig.add
        if trig.stacks_from:
            add = self.status_stacks(trig.stacks_from, t)
            if not add:
                return False
        md.last_trigger = t
        dur = math.inf if (trig.duration == 0 or trig.duration == math.inf) else trig.duration
        md.stacks = [x for x in md.stacks if x > t]
        if self.refresh_stacks and md.stacks:
            md.stacks = [t + dur] * len(md.stacks)
        md.stacks += [t + dur] * add
        if len(md.stacks) > trig.max_stacks:
            md.stacks.sort()
            md.stacks = md.stacks[-trig.max_stacks:]
        return True

    def fire_proc(self, m: _Member, p: HitSpec, t: float) -> bool:
        """A proc's event matched: fire it unless its ICD, condition, cost, pools or every-Nth say no.
        Returns whether it fired."""
        chancy = p.chance < 1
        key = (m.idx, p)
        if not (chancy or t >= self.proc_ready[key] - 1e-9):
            return False
        if p.when and not self.condition(p.when, t):
            return False
        if p.cost and any(m.resources[r] < c - 1e-9 for r, c in p.cost):
            return False   # not enough of the resource: the proc doesn't fire (nothing is spent)
        if p.summon and all(self.pool_blocked(m, pool) for pool in p.summon):
            return False   # every pool it summons into is full and refuses new ones (at_max: block)
        if p.every > 1:
            self.proc_count[key] += 1
            if self.proc_count[key] % p.every:
                return False
        mass = 1.0
        if chancy:   # expected value: the proc's share of this event, with its ICD in expectation
            eicd = self.proc_expected.get(key)
            if eicd is None:
                eicd = self.proc_expected[key] = ExpectedICD(p.chance, p.icd or 0.0)
            mass = eicd.fire(t)
            if mass <= 0:
                return False
        else:
            self.proc_ready[key] = t + (p.icd or 0.0)
        if p.resilience:
            amount = float(p.resilience) * mass * self.team.enemy.resilience
            self.resilience_by_member[m.idx] += amount
            if self.bar:
                self.bar.damage(t, amount)
        if p.energy:   # flat: Charge Efficiency applies to Energy from hits, not to this
            m.energy += float(p.energy) * mass
        for r, c in p.cost:
            m.resources[r] -= c
        for r, g in p.gain:
            self.gain_resource(m, r, g * mass, t)
        if chancy:
            if not p.hit_id:
                return True
            p = replace(p, mult=p.mult * mass)
        if p.restart:   # e.g. a refreshed DoT: the previous firing's pending ticks are dropped
            rkey = f"rproc#{m.idx}#{id(p)}"
            self.restart_gen[rkey] += 1
            self.schedule(m, p, "proc", t, f"{rkey}#{self.restart_gen[rkey]}")
        else:
            self.schedule(m, p, "proc", t, f"proc#{self.seq}")
        return True

    def pool_event(self, m: _Member, pool: str, ms: MinionSpec, ev: str, t: float):
        """An event a minion pool listens to: reactions, sacrifice, resummon or a summon schedule."""
        out = self.alive[(m.idx, pool)]
        key = ("pool", m.idx, pool)
        for ri, h in enumerate(ms.reactions):   # each minion out reacts, with its own ICD
            if not out or not self.event_ok(h.event, ev, t, key + ("react", ri)):
                continue
            for mn in list(out):
                if t >= mn["ready"].get(ri, -1e9) - 1e-9:
                    mn["ready"][ri] = t + (h.icd or 0.0)
                    self.schedule(m, h, "minion_react", t, f"react#{mn['uid']}")
        if ms.sacrifice_on and self.event_ok(ms.sacrifice_on, ev, t, key + ("sacrifice",)):
            for mn in list(out):
                self.vanish(m, pool, mn, t, sacrifice=True)
        if ms.resummon_on and self.event_ok(ms.resummon_on, ev, t, key + ("resummon",)):
            k = len(out)
            for mn in list(out):
                self.vanish(m, pool, mn, t)
            for _ in range(k):
                self.summon(m, pool, t)
        if ms.summon and self.event_ok(ms.summon, ev, t, key + ("summon",)):
            key = f"summon#{m.idx}#{pool}"
            if ms.restart:
                self.restart_gen[key] += 1
            for k in range(ms.count):
                self.push(t + ms.offset + k * ms.every, m.idx, None, "summon", f"{key}#{self.restart_gen[key]}")

    def gain_resource(self, m: _Member, r: str, amount: float, t: float):
        """Add to a resource (capped); emits gain:<who>:<name> once per whole unit gained."""
        old = m.resources[r]
        new = min(m.res_max[r], old + amount)
        m.resources[r] = new
        for _ in range(int(math.floor(new + 1e-9) - math.floor(old + 1e-9))):
            self.emit(f"gain:{m.idx}:{r}", t)

    # ---------------------------------------------------------------- minions

    def pool_blocked(self, m: _Member, pool: str) -> bool:
        ms = m.minions.get(pool)
        return ms is None or (ms.at_max == "block" and len(self.alive[(m.idx, pool)]) >= ms.max)

    def summon(self, m: _Member, pool: str, t: float):
        ms = m.minions[pool]
        self.minion_uid += 1
        mn = {"uid": self.minion_uid, "expire": t + ms.duration, "k": 0,
              "ready": {ri: t + (h.icd or 0.0) for ri, h in enumerate(ms.reactions)}}   # ICD starts at the summon
        self.alive[(m.idx, pool)].append(mn)
        if ms.attacks:
            self.push(t + ms.windup, m.idx, None, "minion_attack", f"{pool}#{mn['uid']}")
        self.emit(f"summon:{m.idx}:{pool}", t)

    def vanish(self, m: _Member, pool: str, mn: dict, t: float, sacrifice: bool = False):
        lst = self.alive[(m.idx, pool)]
        if mn not in lst:
            return
        lst.remove(mn)
        self.emit(f"vanish:{m.idx}:{pool}", t)
        if sacrifice:
            self.emit(f"sacrifice:{m.idx}:{pool}", t)

    def summon_tick(self, m: _Member, pool: str, t: float):
        """One summon tick: a new minion, unless `max` are out: then the oldest is replaced or all are refreshed."""
        ms = m.minions[pool]
        lst = self.alive[(m.idx, pool)]
        self.emit(f"minion_tick:{m.idx}:{pool}", t)
        if len(lst) >= ms.max:
            if ms.at_max == "block":   # full: no new one (e.g. a turret limit)
                return
            if ms.at_max == "refresh":
                for mn in lst:
                    mn["expire"] = t + ms.duration
                return
            self.vanish(m, pool, lst[0], t)
        self.summon(m, pool, t)

    def minion_attack(self, ht: float, mi: int, cid: str):
        """A minion's attack comes up: it queues the hits of its next attack in the cycle, and the attack after."""
        pool, _, uid = cid.partition("#")
        m = self.members[mi]
        mn = next((x for x in self.alive[(mi, pool)] if x["uid"] == int(uid)), None)
        if mn is None or mn["expire"] < ht - 1e-9:
            return
        ms = m.minions[pool]
        h = ms.attacks[mn["k"] % len(ms.attacks)]
        mn["k"] += 1
        self.push(ht + ms.interval / (1.0 + ms.speed), mi, None, "minion_attack", cid)
        for k in range(h.count):   # queued, so later hits see the buffs of their own moment and stop at the fight's end
            self.push(ht + k * h.interval, mi, h, "minion", cid)

    # ---------------------------------------------------------------- casts and cooldowns

    def push(self, t: float, mi: int, h: HitSpec | None, action: str, cid: str):
        self.seq += 1
        heapq.heappush(self.queue, (t, self.seq, mi, h, action, cid))

    def schedule(self, m: _Member, h: HitSpec, action: str, t: float, cid: str, cut_at: float = math.inf):
        for k in range(h.count):
            if h.offset + k * h.interval > cut_at + 1e-9:   # a dodge-cancel drops the hits still to come
                break
            self.push(t + h.offset + k * h.interval, m.idx, h, action, cid)

    @staticmethod
    def refill(m: _Member, name: str, t: float):
        q = m.recharge[name]
        while q and q[0] <= t + 1e-9:
            q.pop(0)
            m.charges[name] += 1

    def ready(self, m: _Member, name: str, t: float) -> bool:
        if name in m.max_charges:   # stored uses: recharged one at a time, UseInterval between uses
            self.refill(m, name, t)
            return m.charges[name] > 0 and t >= m.last_use[name] + m.use_interval[name] - 1e-9
        return t >= m.cd_ready[name] - 1e-9

    @staticmethod
    def give_charge(m: _Member, name: str, t: float):
        """A cooldown reset on a charged action: the use recharging now is ready; the rest move up."""
        q = m.recharge[name]
        if q:
            shift = q[0] - t
            q.pop(0)
            m.recharge[name] = [x - shift for x in q]
            m.charges[name] += 1

    def cooldown(self, m: _Member, name: str, start: float) -> float:
        """The cooldown of an action starting at `start`: a `cd_when` window scales it if it holds at that moment."""
        cd = m.cd.get(name, 0.0)
        for action, scale, when in m.cd_when:
            if action == name and self.condition(when, start):
                cd *= scale
        return cd

    def cast(self, m: _Member, name: str, t: float, from_cd: bool = True):
        a = m.actions[name]
        m.cast_count[name] += 1
        self.first_cast.setdefault((m.idx, name), round(t, 6))
        self.last_cast[(m.idx, name)] = t
        cid = f"{name}#{m.cast_count[name]}"
        c = m.cast_count[name]
        # A dodge-cancelled cast (the main loop handles autos) loses the hits after the dodge and ends early. The cancel
        # is the cast's own `dodge_cancel` or that of the followup it leads into.
        cancel = None
        if m.idx == 0 and self.team.assumptions.get("dodge_cancel", True):
            fu = next((fa.followup for fa in m.actions.values() if fa.followup and fa.followup.dodge_at is not None
                       and not fa.followup.event and fa.followup.after == name and c % fa.followup.every == 0), None)
            cancel = (a.dodge_at, a.dodge_duration) if a.dodge_at is not None else \
                (fu.dodge_at, fu.dodge_duration) if fu else None
        cut_at, lock = cancel if cancel else (math.inf, a.lock)
        for h in a.hits:
            if h.cycle and (c - 1) % h.cycle[0] != h.cycle[1] - 1:
                continue
            if (h.from_cast and c < h.from_cast) or (h.upto_cast and c > h.upto_cast):
                continue
            self.schedule(m, h, name, t, cid, cut_at)
        self.start_cooldowns(m, name, a, t, lock, cut_at, from_cd)
        if name == "ult":
            m.energy = 0.0
        if name in m.kit.on_field:
            self.on_field_until[m.idx] = max(self.on_field_until[m.idx], t + m.kit.on_field[name])
        if m.idx == 0:
            self.main_after_cast(m, name, t, lock, cut_at if cancel else None, from_cd)
        self.emit(f"cast:{m.idx}:{name}", t)

    def start_cooldowns(self, m: _Member, name: str, a: ActionSpec, t: float, lock: float, cut_at: float,
                        from_cd: bool):
        """The cast's own cooldown (or stored charge), the cooldown it starts, and the one it resets."""
        reduce = sum(cr["seconds"] * cr["times"] for cr in m.cd_reduce if cr["action"] == name)
        if from_cd and name in m.max_charges:
            self.refill(m, name, t)
            m.charges[name] -= 1
            m.last_use[name] = t
            q = m.recharge[name]
            q.append(max(t, q[-1] if q else t) + self.cooldown(m, name, t) - reduce)   # one recharge timer, progress kept across casts (user)
        elif from_cd:
            m.cd_ready[name] = t + a.cd_start + self.cooldown(m, name, t + a.cd_start) - reduce
        if a.starts_cd and a.starts_cd in m.cd:
            start = t + min(lock, cut_at)   # user: a dodge starts it at once
            m.cd_ready[a.starts_cd] = start + self.cooldown(m, a.starts_cd, start)
        tgt = m.reset_cd.get(name)
        if tgt:
            if tgt in m.max_charges:
                self.give_charge(m, tgt, t)
            else:
                m.cd_ready[tgt] = t

    def main_after_cast(self, m: _Member, name: str, t: float, lock: float, dodge_at: float | None, from_cd: bool):
        """The main is locked and busy, its auto string restarts, and extra casts and followups are queued."""
        self.lock_until = max(self.lock_until, t + lock)
        self.busy_until = t + min(DEFAULT_BUSY, lock) if lock else t
        if dodge_at is not None:
            bisect.insort(self.cancel_dodges, t + dodge_at)
        if self.auto_clock > 0:
            self.auto_loop += 1
        self.auto_clock = 0.0
        for _ in range(m.extra_casts.get(name, 0) if from_cd else 0):
            self.pending.append((t + DEFAULT_BUSY, name))
        for fname, fa in m.actions.items():
            if fa.followup and not fa.followup.event and fa.followup.after == name \
                    and m.cast_count[name] % fa.followup.every == 0:
                self.pending.append((t + lock + fa.followup.delay, fname))
                if not fa.followup.autos:   # no autos before the followup
                    self.lock_until = max(self.lock_until, t + lock + fa.followup.delay)

    def held(self, m: _Member, name: str, t: float) -> bool:
        """Team-file rotation timing: a ready action waits until `until` holds (at most `max_wait` s). With `only_if`,
        it only starts waiting if that holds when the action becomes ready (e.g. "wait if Cosette's skill shows <= 3 s")."""
        rule = self.holds.get((m.idx, name))
        if not rule:
            return False
        until, max_wait, only_if = rule
        key = (m.idx, name)
        if self.condition(until, t):
            self.hold_since.pop(key, None)
            return False
        if key not in self.hold_since and only_if and not self.condition(only_if, t):
            return False
        start = self.hold_since.setdefault(key, t)
        if t - start >= max_wait:
            self.hold_since.pop(key, None)
            return False
        return True

    # ---------------------------------------------------------------- stat sheets

    def stat_plan(self, receiver_block: StatBlock, receiver, tags_key: tuple, minion: bool) -> tuple:
        tags = set(tags_key)
        s = receiver_block.copy()
        all_reach = self.all_reach

        def applies(md: _Mod) -> bool:
            return receiver in md.receivers and (not md.mod.hit_tags or bool(tags & set(md.mod.hit_tags)))
        for md in self.scoped_const:   # always on (snapshot) or averaged uptime (minion check)
            if applies(md) and (not minion or _const_reaches_minions(md.mod, all_reach)):
                s.add_stat(md.mod.stat, md.mod.value * md.constant, md.mod.is_pct)
        ok = (lambda md: _reaches_minions(md.mod, all_reach)) if minion else (lambda md: True)
        plan = (s, [md for md in self.by_event if applies(md) and ok(md)],
                [md for md in self.while_mods if applies(md) and ok(md)], [None, None])
        self.stat_plans[(receiver, minion, tags_key)] = plan
        return plan

    def stat_for(self, receiver_block: StatBlock, receiver, tags_key: tuple, t: float, minion: bool = False) -> StatBlock:
        """The receiver's sheet for a hit with these tags at time t. Which modifiers can apply depends only on
        (receiver, tags), so that part is planned once; `receiver_block` is fixed per (receiver, minion)."""
        plan = self.stat_plans.get((receiver, minion, tags_key)) or self.stat_plan(receiver_block, receiver, tags_key,
                                                                                    minion)
        base, ev_mods, wh_mods, last = plan
        sig = []   # stacks up per event mod, then the multiplier per while mod: the sheet is a function of these
        for md in ev_mods:
            st = md.stacks
            if not st:
                sig.append(0)
            elif len(st) == 1:
                sig.append(1 if st[0] > t else 0)
            else:
                sig.append(sum(1 for x in st if x > t))
        for md in wh_mods:
            sig.append(self.condition(md.event, t))
        if last[0] == sig:
            return last[1]   # callers only read the sheet
        s = base.copy()
        i = 0
        for md in ev_mods:
            k = sig[i]
            i += 1
            if k:
                mod = md.mod
                s.add_stat(mod.stat, mod.value * k, mod.is_pct)
        for md in wh_mods:
            c = sig[i]
            i += 1
            if c:
                mod = md.mod
                k = c if mod.trigger.per_stack else mod.trigger.max_stacks
                s.add_stat(mod.stat, mod.value * k, mod.is_pct)
        last[0], last[1] = sig, s
        return s

    # ---------------------------------------------------------------- hits

    def get_hit(self, hid):
        h = self.hit_cache.get(hid)
        if h is None:
            h = self.hit_cache[hid] = hit(self.gd, hid)
        return h

    def apply_mark(self, mi: int, t: float):
        """Member `mi` inflicts their element's Mark on the enemy."""
        el = self.elements[mi]
        was_up = self.mark_up[el]
        self.mark_up[el] = True
        self.emit(f"mark_applied:{mi}", t)
        self.emit(f"mark_refresh:{mi}" if was_up else f"mark_new:{mi}", t)

    def land(self, t: float, mi: int, h: HitSpec, action: str, cid: str):
        m = self.members[mi]
        for pool in h.summon:   # e.g. a proc that spends Resource Markers to put out a turret
            if pool in m.minions:
                self.summon_tick(m, pool, t)
        if h.hit_id == 0:   # marker: no damage, only emits marker:<who>:<tag> (and can inflict a Mark)
            for tag in h.tags:
                self.emit(f"marker:{mi}:{tag}", t)
            if h.applies_mark:   # e.g. Ann's wind wall "constantly inflicts" Breeze without dealing DMG
                self.apply_mark(mi, t)
            return
        hd = self.get_hit(h.hit_id)
        tags_key = h.tags if type(h.tags) is tuple else tuple(h.tags)
        tags = set(tags_key)
        lv = hit_level(hd, m.skill_levels, m.pot_levels, fallback="auto" if action == "auto" else (
            "ult" if action == "ult" else "skill"))
        slot = slot_of(hd)
        minion = slot == "minion"
        attacker = self.stat_for(m.minion_static if minion else m.static, mi, tags_key, t, minion)
        taken = self.stat_for(self.enemy_static, "enemy",
                              (tags_key + ("by_main" if mi == 0 else "by_support", f"{slot}_dmg"))
                              if self.enemy_tags else tags_key, t)
        dmg_unbroken = self.raw_damage(hd, lv, attacker, taken) * h.mult
        bar = self.bar
        dmg = dmg_unbroken * (bar.ratio(t) if bar else 1.0)   # read before this hit lowers the bar
        res = dmg_unbroken * self.adjust[mi] * (1 + attacker.get(RES_BREAK_EFF))
        self.resilience_by_member[mi] += res
        if bar:
            bar.damage(t, res)
        self.by_slot[(mi, slot)] += dmg
        for tag in (*tags, f"{slot}_dmg"):
            self.last_hit[(mi, tag)] = t
        self.by_member[mi] += dmg
        if mi == 0 and hd.energy:
            self.charge_energy(hd, action, cid, t)
        el = self.elements[mi]   # Marks are per element: a Trekker applies and triggers Marks of their own element
        if h.applies_mark:
            self.apply_mark(mi, t)
        triggers = h.triggers_mark or bool(tags & m.mark_tags)
        # Any member whose kit has a mark hit can trigger (consume) the Mark: supports like Shia compete with the main.
        if triggers and self.mark_up[el] and t >= self.next_mark[el] - 1e-9 and m.kit.mark_hit:
            self.mark_up[el] = False
            self.next_mark[el] = t + self.team.mark_icd
            self.push(t, mi, HitSpec(hit_id=m.kit.mark_hit, tags=("mark",) + m.kit.mark_hit_tags), "mark", "mark")
            self.emit(f"mark:{mi}", t)
        for tag in tags:
            self.emit(f"hit:{mi}:{tag}", t)
        self.emit(f"hit:{mi}:{slot}_dmg", t)
        self.emit(f"damage:{mi}", t)   # once per landed hit, however many tags it has

    def raw_damage(self, hd, lv: int, attacker: StatBlock, taken: StatBlock) -> float:
        """A hit's damage before its own multiplier and the break bar.

        stat_for hands back the same sheets while no buff changed, and the damage only depends on them, so it's
        memoised per hit. Tests observe hits by patching `hit_damage`: a patched one is called for every hit."""
        memo = self.dmg_memo.get((hd.id, lv)) if hit_damage is _HIT_DAMAGE else None
        if memo is not None and memo[0] is attacker and memo[1] is taken:
            return memo[2]
        en = self.team.enemy
        # DEF reductions on the enemy (flat, then %) lower its DEF before defAmend (formula ref 2.def.c); floor 0
        defense = max(0.0, (en.defense + taken.flat[DEF]) * (1 + taken.pct[DEF]))
        e = Enemy(res=en.res, res_by_element=en.res_by_element, defense=defense, broken=en.broken,
                  vul=en.vul, taken=taken)
        raw = hit_damage(hd, lv, attacker, e)
        self.dmg_memo[(hd.id, lv)] = (attacker, taken, raw)
        return raw

    def charge_energy(self, hd, action: str, cid: str, t: float):
        """The main's hits charge the main, and the supports get a share (capped per cast by GetEnergyLimit)."""
        cap = self.main.energy_cap.get(action, math.inf)
        gain = max(0.0, min(hd.energy, cap - self.energy_used[cid]))
        self.energy_used[cid] += gain
        for mm in self.members:
            eff = mm.charge + (self.stat_for(mm.static, mm.idx, (), t).get(CHARGE_EFF) if self.has_charge_mods
                               else 0.0)
            mm.energy += gain * (1.0 if mm.idx == 0 else mm.kit.energy_conv) * eff

    # ---------------------------------------------------------------- the timeline

    def _setup_autos(self):
        auto = self.main.actions.get("auto")
        self.auto_hits = []   # (offset within the string, HitSpec with count 1)
        if auto and auto.duration > 0:
            for h in auto.hits:
                for k in range(h.count):
                    self.auto_hits.append((h.offset + k * h.interval,
                                           HitSpec(**{**h.__dict__, "count": 1, "offset": 0.0})))
            self.auto_hits.sort(key=lambda x: x[0])
        # Dodge-cancel (Nanoha): dodging at the end of each auto string shortens it, so the main dodges every string and
        # those dodges replace the periodic ones (user, 2026-11-04).
        self.cancel_at = auto.dodge_at if (auto and auto.dodge_at is not None
                                           and self.team.assumptions.get("dodge_cancel", True)) else None
        self.auto_len = auto.dodge_duration if self.cancel_at is not None else (auto.duration if auto else 0.0)

    def set_dodges(self, extra: list):
        """Clock events: `timer:<s>` fires at 0, s, 2s, ... ("after the battle begins ... once every 20 s");
        `dodge:0` is the main's dodge, one every `dodge_interval` s on average (assumption, default 10);
        `hit_taken:0` the main being hit, one every `hit_taken_interval` s."""
        assumptions = self.team.assumptions
        used = " ".join([md.event for md in self.by_event] + [r for md in self.by_event for r in md.mod.trigger.reset_on or ()]
                         + [pev for m in self.members for pev, _ in m.procs]
                         + [ev for m in self.members for ms in m.minions.values()
                            for ev in (ms.summon, ms.sacrifice_on, ms.resummon_on, *(h.event for h in ms.reactions))]
                         + [fev for _, fev, _ in self.main_event_followups])
        self.timers = sorted({float(x) for x in re.findall(r"\btimer:(\d+(?:\.\d+)?)", used)})
        dodge_every = float(assumptions.get("dodge_interval", 10.0))
        spam = assumptions.get("dodge_spam")   # {interval: 3, potentials: [ids]}: dodge faster when the main has one
        if spam:
            owned = set(self.main.pot_levels) | {x.potential_id for (j, x) in extra
                                                 if j == 0 and isinstance(x, ResolvedPotential)}
            want = set(spam.get("potentials") or [])
            if not want or owned & want:
                dodge_every = float(spam["interval"])
        self.dodge_time = float(assumptions.get("dodge_time", 10 / 30))   # user: a dodge costs 10 frames of attacking
        self.next_dodge = dodge_every
        if self.cancel_at is not None:
            dodge_every = 0.0
        self.dodge_every = dodge_every
        self.hit_every = float(assumptions.get("hit_taken_interval", 20.0))   # `hit_taken:0`: the main is hit (~20 s)

    def run(self):
        # A status name that is a plain name and not also a minion pool is up exactly when one of its mods has a live
        # stack. Names that are also pools are timed with the pools (once).
        self.named_plain = [(name, mds) for name, mds in self.named.items()
                            if not ("+" in name or ">=" in name or name in self.pools)]
        self.named_other = [name for name in self.named if ("+" in name or ">=" in name) and name not in self.pools]
        cast_order = self.members[1:] + [self.main]
        dt = self.dt
        for step in range(int(round(self.T / dt)) + 1):
            t = step * dt
            self.clock_events(t)
            self.track_time(t)
            for (mi, pool), lst in list(self.alive.items()):   # minion lifetimes
                for mn in [x for x in lst if x["expire"] <= t + 1e-9]:
                    self.vanish(self.members[mi], pool, mn, t)
            for m in cast_order:   # supports first, then main
                self.try_cast(m, t)
            if self.auto_hits and t >= self.lock_until - 1e-9:
                self.autos(t)
            self.land_due(t)

    def clock_events(self, t: float):
        """Timers, dodges and the boss's attacks."""
        dt = self.dt
        for per in self.timers:
            if per > 0 and abs(t / per - round(t / per)) * per < dt / 2:
                self.emit(f"timer:{per:g}", t)
        # A dodge cancelling an action (Amber) is free and takes the place of the next periodic one.
        while self.cancel_dodges and t >= self.cancel_dodges[0] - 1e-9:
            self.cancel_dodges.pop(0)
            self.emit("dodge:0", t)
            self.next_dodge += self.dodge_every
        # Dodges need control: one due during a cast's lock (no control, but immune) waits for the lock to end.
        # The schedule keeps its average rate (user: the 1 per 10 s came from real fights, locks included), but two
        # dodges are at least DODGE_CD apart. Each pauses the auto string for `dodge_time`.
        if self.dodge_every > 0 and t >= self.next_dodge - 1e-9 and t >= self.lock_until - 1e-9:
            self.lock_until = max(self.lock_until, t + self.dodge_time)   # first, so a follow-up waits for the dodge
            self.emit("dodge:0", t)
            self.next_dodge = max(self.next_dodge + self.dodge_every, t + min(DODGE_CD, self.dodge_every))
        hit_every = self.hit_every
        if hit_every > 0 and t > 0 and abs(t / hit_every - round(t / hit_every)) * hit_every < dt / 2 \
                and not (self.bar is not None and self.bar.broken(t)):   # a broken boss doesn't attack (user)
            self.emit("hit_taken:0", t)

    def track_time(self, t: float):
        """Passive energy, time on the field (and its events) and status uptimes."""
        dt = self.dt
        for m in self.members:
            m.energy += m.kit.energy_per_second * dt
            if self.on_field_until[m.idx] > t:
                before = self.on_field_time[m.idx]
                self.on_field_time[m.idx] += dt
                if int((self.on_field_time[m.idx] + 1e-9) // 5.0) > int((before + 1e-9) // 5.0):
                    self.emit(f"on_field_5s:{m.idx}", t)   # "every 5 s they are on the field"
                if int(self.on_field_time[m.idx] + 1e-9) > int(before + 1e-9):
                    self.emit(f"on_field_1s:{m.idx}", t)   # every second on the field
        status_time = self.status_time
        for name, mds in self.named_plain:
            if any(md.stacks and max(md.stacks) > t for md in mds):
                status_time[name] += dt
        for name in self.named_other:
            if self.status_stacks(name, t) > 0:
                status_time[name] += dt
        for pool in self.pools:
            if self.status_stacks(pool, t) > 0:
                status_time[pool] += dt

    def try_cast(self, m: _Member, t: float):
        """A member's next cast this tick, if any: the main's queued followups first, then the ult, then the skill."""
        is_main = m.idx == 0
        if is_main and t < self.busy_until - 1e-9:
            return
        if not is_main and m.kit.wait_on_field and self.on_field_until[m.idx] > t + 1e-9:
            return
        if is_main and self.pending:
            self.pending.sort()
            if self.pending[0][0] <= t + 1e-9:
                _, name = self.pending.pop(0)
                self.cast(m, name, t, from_cd=False)
                return
        if "ult" in m.actions and m.ult_cost and m.energy >= m.ult_cost and self.ready(m, "ult", t) \
                and not self.held(m, "ult", t):
            self.cast(m, "ult", t)
            return
        if "skill" in m.actions and self.ready(m, "skill", t):
            if is_main and t < 1.0 - 1e-9:
                return
            if self.held(m, "skill", t):
                return
            self.cast(m, "skill", t)

    def autos(self, t: float):
        """The main's auto string, which restarts after every cast. ATK SPD runs the whole string faster, shots and
        reload (user-timed shots; the reload is a GUESS)."""
        speed = 1.0 + (self.stat_for(self.main.static, 0, (), t).get(ATK_SPD) if self.has_atk_spd else 0.0)
        c0, c1 = self.auto_clock, self.auto_clock + self.dt * speed
        for off, h in self.auto_hits:
            if c0 - 1e-9 <= off < c1 - 1e-9:
                self.push(t, 0, h, "auto", f"auto#{self.auto_loop}#{h.hit_id}")
        if self.cancel_at is not None and c0 - 1e-9 <= self.cancel_at < c1 - 1e-9:
            self.emit("dodge:0", t)
        if c1 >= self.auto_len - 1e-9:
            c1 = 0.0
            self.auto_loop += 1
            self.main.cast_count["auto"] += 1
        self.auto_clock = c1

    def land_due(self, t: float):
        """Everything queued up to t: hits, summon ticks and minion attacks."""
        queue = self.queue
        while queue and queue[0][0] <= t + 1e-9:
            ht, _, mi, h, action, cid = heapq.heappop(queue)
            if ht > self.T:
                continue
            if cid.startswith(("rproc#", "summon#")):
                key, _, gen = cid.rpartition("#")
                if int(gen) != self.restart_gen[key]:
                    continue   # superseded by a newer firing / schedule
            if action == "summon":
                self.summon_tick(self.members[mi], cid.split("#")[2], ht)
            elif action == "minion_attack":
                self.minion_attack(ht, mi, cid)
            else:
                self.land(ht, mi, h, action, cid)

    def result(self) -> SimResult:
        members, bar = self.members, self.bar
        casts = {(m.idx, a): c for m in members for a, c in m.cast_count.items()}
        for m in members:
            for a in m.actions:
                casts.setdefault((m.idx, a), 0)
        return SimResult(total=sum(self.by_member.values()), by_member=dict(self.by_member), by_slot=dict(self.by_slot),
                         casts=casts, first_cast=self.first_cast, unknown_modifiers=sorted(self.unknown),
                         on_field_time=dict(enumerate(self.on_field_time)), status_time=dict(self.status_time),
                         breaks=list(bar.breaks) if bar else [], broken_time=bar.broken_time(self.T) if bar else 0.0,
                         resilience_by_member=dict(self.resilience_by_member))
