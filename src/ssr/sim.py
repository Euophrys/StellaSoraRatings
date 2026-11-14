"""Tick-based 120 s fight simulation producing total team damage."""
from __future__ import annotations

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
from .kit import ActionSpec, HitSpec, MinionSpec, ResolvedPotential, kit_buffs, resolve_buffs, resolve_potential
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
    if "|" in ev:
        return "|".join(_norm_event(e, owner) for e in ev.split("|"))
    base, amp, rest = ev.partition("&")   # "&recent:..." / "&while:..." suffixes keep their own tokens
    parts = base.split(":")
    return ":".join([parts[0]] + [{"self": str(owner), "main": "0"}.get(p, p) for p in parts[1:]]) + amp + rest


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
    once_used: set = field(default_factory=set)   # "&once" event alternatives already used


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
    n = len(team.members)
    extra = extra or []
    discs_main, discs_support = discs if discs is not None else (team.discs_main, team.discs_support)
    unknown: set[str] = set()
    uptime_default = float(team.assumptions.get("unknown_trigger_uptime", 1.0))
    # A new stack of a buff resets every stack's timer (user, in game: Gerie's Delight in Ruin, 6 stacks all drop at
    # once; BuffValue TimeSuperposition 2 on nearly every buff). "independent" lets each stack expire on its own.
    refresh_stacks = team.assumptions.get("stack_timers", "refresh") == "refresh"
    disc_team = team.assumptions.get("disc_stats_target", "team") == "team"

    classes = [gd.table("Character")[str(m.char_id)].get("Class", 0) for m in team.members]
    elements = [gd.table("Character")[str(m.char_id)].get("EET", 0) for m in team.members]

    # ---- per-member setup: potentials, actions, levels
    members: list[_Member] = []
    mods: list[_Mod] = []

    def add_mod(m: Modifier, owner: int, src_target: str | None = None, element: int = 0):
        if m.main_element and elements[0] != m.main_element:
            return   # "the main <Element> Trekker": the main isn't that element
        tgt = src_target or m.target
        rec = _targets(tgt, owner, n, classes, elements)
        if element:   # element-locked disc: only that element's Trekkers (or the enemy, if any are in the team)
            if element not in elements:
                return
            rec = [r for r in rec if r == "enemy" or elements[r] == element]
            if not rec:
                return
        t = m.trigger
        if t is None:
            mods.append(_Mod(m, owner, rec))
            return
        if t.uptime is not None or t.event == "unknown":
            up = t.uptime if t.uptime is not None else uptime_default
            if t.uptime is None:
                unknown.add(f"{m.source}: {m.label()} (uptime {up:g} x {t.max_stacks} stacks assumed)")
            mods.append(_Mod(m, owner, rec, constant=up * t.max_stacks))
            return
        mods.append(_Mod(m, owner, rec, event=_norm_event(_expand_who(t.event, n, classes, elements), owner)))

    for i, mc in enumerate(team.members):
        kit = mc.kit
        levels = dict(mc.skill_levels)
        if emblems:
            for e in mc.emblems:
                if isinstance(e, EmblemSkillLevel) and e.applies_to(mc.role):
                    levels[e.action] = levels.get(e.action, 10) + e.plus
        for (j, x) in extra:
            if j == i and isinstance(x, EmblemSkillLevel) and x.applies_to(mc.role):
                levels[x.action] = levels.get(x.action, 10) + x.plus
        pot_levels = {p: 1 for p in mc.pinks}
        pot_levels.update(build.levels_for(mc.char_id))
        lines_i = (list(mc.emblems) if emblems else []) + [x for (j, x) in extra if j == i]
        for x in lines_i:   # Lv90 "+N": fights at target + N (cap 9); not taken still fights at N
            if isinstance(x, EmblemPotentialLevel) and line_relevant(x, 0, mc.role):
                pot_levels[x.potential_id] = min(9, pot_levels.get(x.potential_id, 0) + x.plus)
        charge = 1.0 + sum(x.value for x in lines_i
                           if isinstance(x, EmblemChargeEfficiency) and x.role == mc.role)
        resolved = [_potential(gd, kit, p, lv) for p, lv in pot_levels.items()]
        resolved += [x for (j, x) in extra if j == i and isinstance(x, ResolvedPotential)]
        owned = set(pot_levels)
        # A potential that `excludes` another in the build does nothing (it still counts as owned for hits'
        # requires/excludes, and for its level).
        resolved = [rp for rp in resolved if not owned & set(rp.excludes)]

        def keep(h: HitSpec) -> bool:
            return ((not h.requires or any(r in owned for r in h.requires)) and not any(e in owned for e in h.excludes)
                    and all(r in owned for r in h.requires_all))

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

        if kit.ult_only_with and not set(kit.ult_only_with) & {x.char_id for x in team.members}:
            actions.pop("ult", None)

        m = _Member(
            idx=i, cfg=mc, kit=kit, actions=actions, skill_levels=levels, pot_levels=pot_levels,
            mark_tags={t for rp in resolved for t in rp.mark_tags},
            extra_casts={k: v for rp in resolved for k, v in rp.extra_casts.items()},
            reset_cd={**kit.reset_cd, **{k: v for rp in resolved for k, v in rp.reset_cd.items()}},
            cd_reduce=[rp.cd_reduce for rp in resolved if rp.cd_reduce],
            cd_when=[(c["action"], float(c["scale"]), _norm_event(c["when"], i)) for rp in resolved for c in rp.cd_when],
            procs=[(_norm_event(_expand_who(p.event, n, classes, elements), i),
                    replace(p, when=_norm_event(p.when, i), gain=tuple((r, float(v)) for r, v in p.gain),
                            cost=tuple((r, float(v)) for r, v in p.cost)) if (p.when or p.gain or p.cost) else p)
                   for p in [*kit.procs, *(p for rp in resolved for p in rp.procs)] if keep(p)],
        )
        m.res_max = dict(kit.resources)
        m.resources = {r: 0.0 for r in kit.resources}
        for _, p in m.procs:
            if p.chance < 1 and p.restart:
                raise ValueError(f"{gd.char_name(mc.char_id)}: proc {p.hit_id} on {p.event!r}: `chance` with `restart` "
                                 "isn't supported (an expected-value refreshed DoT isn't modelled)")
            if p.chance < 1 and (p.cost or p.summon):
                raise ValueError(f"{gd.char_name(mc.char_id)}: proc {p.hit_id} on {p.event!r}: `chance` with `cost` "
                                 "or `summon` isn't supported (an expected-value spend or summon isn't modelled)")
            for r, _ in (*p.gain, *p.cost):
                if r not in kit.resources:
                    raise ValueError(f"{gd.char_name(mc.char_id)}: proc {p.hit_id} uses resource {r!r}, "
                                     "which the kit section's `resources:` doesn't declare")
        for name, a in actions.items():
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
        for pool, ms in kit.minions.items():
            rules, adds = {}, defaultdict(float)
            for rp in resolved:
                for k, v in rp.minion_rules.get(pool, {}).items():
                    if k.endswith("_add"):   # additive, e.g. duration_add: +3 s of lifetime
                        adds[k[:-4]] += float(v)
                    else:
                        rules[k] = v
            ms = replace(ms, **rules)
            ms = replace(ms, **{k: getattr(ms, k) + v for k, v in adds.items()})
            m.minions[pool] = replace(ms, summon=_norm_event(ms.summon, i),
                                      sacrifice_on=_norm_event(ms.sacrifice_on, i) if ms.sacrifice_on else "",
                                      resummon_on=_norm_event(ms.resummon_on, i) if ms.resummon_on else "",
                                      attacks=[h for h in ms.attacks if keep(h)],
                                      reactions=[replace(h, event=_norm_event(_expand_who(h.event, n, classes, elements), i))
                                                 for h in ms.reactions if keep(h)])
        if "ult" in actions and actions["ult"].skill_id:
            m.ult_cost = ult_energy(gd, actions["ult"].skill_id)
            for rp in resolved:
                m.ult_cost *= rp.ult_cost_scale
        m.charge = charge
        members.append(m)

        for rp in resolved:
            for md in rp.modifiers:
                add_mod(md, i)
        talent_effects, talent_keys = talent_nodes(gd, mc.char_id, mc.talents)
        for eid in talent_effects:
            for md in effect_modifiers(gd, eid, f"{gd.char_name(mc.char_id)} talent node ({eid})"):
                add_mod(md, i)
        for tid in talent_keys:
            if tid not in kit.talents:
                unknown.add(f"{gd.char_name(mc.char_id)} key talent {tid}: not in the kit spec, not modelled")
        for md in resolve_buffs(gd, kit, levels, owned, kit_buffs(kit, talent_keys)):
            add_mod(md, i)
        for (j, x) in extra:
            if j == i and isinstance(x, Modifier):
                add_mod(x, i)

    # ---- static stats: base + discs + emblems
    disc_stats = StatBlock()
    for d, c in list(discs_main) + list(discs_support):
        disc_stats.add(_disc_stats(gd, d, c, team.disc_level))
    for d, c in discs_main:
        el = _disc_element(gd, d)
        for md in _disc_mods(gd, d, c):
            add_mod(md, 0, "team" if (disc_team and md.target == "self") else None, el)
    notes_lv = int(team.assumptions.get("harmony_notes", 1))   # notes for main-disc harmonies at this level
    if notes_lv > 0:
        counts = harmony_note_counts(gd, [d for d, _ in discs_main if d != FILLER], notes_lv)
        for md in note_modifiers(gd, counts):
            add_mod(md, 0, "team" if disc_team else None)
    for md in team.enemy.ability:   # the boss's ability (enemy preset)
        add_mod(md, 0)
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
    enemy_static = team.enemy.taken.copy()
    all_reach = team.assumptions.get("minion_buffs", "text") == "all"

    def reaches_minions(mod: Modifier) -> bool:
        return all_reach or bool(mod.minions) or mod.stat in MINION_STATS

    def const_reaches_minions(mod: Modifier) -> bool:
        """Minions summon with a snapshot of the summoner's sheet at battle start (user, in-game), so truly
        always-on buffs (no trigger) reach them whatever their wording. Buffs that come and go, including those
        averaged as `uptime x stacks`, reach minions only if they name minions / friendly units."""
        return mod.trigger is None or reaches_minions(mod)

    # Fold unscoped always-on mods into static blocks.
    dynamic: list[_Mod] = []
    for md in mods:
        if md.event == "" and not md.mod.hit_tags:
            for r in md.receivers:
                blks = [enemy_static] if r == "enemy" else (
                    [members[r].static] + ([members[r].minion_static] if const_reaches_minions(md.mod) else []))
                for blk in blks:
                    blk.add_stat(md.mod.stat, md.mod.value * md.constant, md.mod.is_pct)
        else:
            dynamic.append(md)
    for m in members:   # "at the start of battle, ... restore N Energy" (always-on, folded into the sheet)
        m.energy = m.static.get(START_ENERGY)
    for md in dynamic:
        if md.mod.needs_scope and not md.mod.hit_tags:
            unknown.add(f"{md.mod.source}: {md.mod.label()} applied to all hits (scope unknown)")
    for md in mods:
        if md.event == "" and md.mod.needs_scope and not md.mod.hit_tags:
            unknown.add(f"{md.mod.source}: {md.mod.label()} applied to all hits (scope unknown)")

    by_event: list[_Mod] = [md for md in dynamic if md.event and not md.event.startswith("while:")]
    while_mods: list[_Mod] = [md for md in dynamic if md.event.startswith("while:")]
    scoped_const: list[_Mod] = [md for md in dynamic if not md.event]
    on_field_until = [0.0] * n
    on_field_time = [0.0] * n
    roles = [m.role for m in team.members]

    named = {md.mod.name: md for md in by_event if md.mod.name}
    status_time: dict = defaultdict(float)

    last_cast: dict = {}   # (member, action) -> time of its last cast
    alive: dict = defaultdict(list)   # (member, pool) -> [{"uid", "expire", "k"}] minions out, oldest first
    pools = {name for m in members for name in m.minions}
    status_parsed: dict = {}   # status expression -> ([(named mod or None, pool name or None)], least stacks)

    def status_stacks(name: str, t: float) -> int:
        """Stacks of a status; "a+b" sums several statuses, "a>=N" is 0 below N stacks.
        A minion pool's name counts its minions out."""
        parsed = status_parsed.get(name)
        if parsed is None:
            names, _, least = name.partition(">=")
            parsed = status_parsed[name] = ([(named.get(nm), nm if nm in pools else None) for nm in names.split("+")],
                                            int(least or 1))
        k = 0
        for md, pool in parsed[0]:
            if md is not None and md.stacks:
                k += sum(1 for x in md.stacks if x > t)
            if pool is not None:
                k += sum(len(v) for (mi, p), v in alive.items() if p == pool)
        return k if k >= parsed[1] else 0

    def condition(ev: str, t: float) -> int:
        """Multiplier for a "while:" modifier at time t (0 = inactive)."""
        parts = ev.split(":")   # while:on_field:<who> | while:status:<name>
        if parts[1] == "not":   # while:not:<condition>: active exactly when the condition isn't
            return int(not condition("while:" + ":".join(parts[2:]), t))
        if parts[1] == "status":
            return status_stacks(parts[2], t)
        if parts[1] == "resource":   # while:resource:<member>:<name>>=N (or >N): that member holds that much
            name, op, want = re.split("(>=?)", parts[3])
            have = members[int(parts[2])].resources.get(name, 0.0)
            return int(have >= float(want) - 1e-9 if op == ">=" else have > float(want) + 1e-9)
        if parts[1] == "cd_within":   # while:cd_within:<member>:<action>:<seconds>: cooldown left <= N s
            mm = members[int(parts[2])]
            left = mm.cd_ready.get(parts[3], 0.0) - t
            return int(left <= float(parts[4]) + 1e-9)
        if parts[1] == "in_action":   # while:in_action:<member>:<action>: within that action's lock after its last cast
            mi, act = int(parts[2]), parts[3]
            last = last_cast.get((mi, act))
            a = members[mi].actions.get(act)
            return int(last is not None and a is not None and t - last <= a.lock + 1e-9)
        if parts[1] == "cast_within":   # while:cast_within:<who>:<action>:<seconds>: cast that recently
            last = last_cast.get((int(parts[2]), parts[3]))
            return int(last is not None and t - last <= float(parts[4]) + 1e-9)
        if parts[1] == "broken":   # while:broken: the enemy's resilience bar is broken
            if bar is None:   # no bar: today's behaviour, the unknown_trigger_uptime assumption (on if > 0)
                return int(team.enemy.breaks and uptime_default > 0)
            return int(bar.broken(t))
        if parts[1] == "vul":   # while:vul:<element>: the enemy has that element's VUL (an <Element> DMG Taken debuff up)
            st = ELEM_TAKEN_BASE + int(parts[2]) - 1
            if enemy_static.get(st) > 0:
                return 1
            return int(any(md.mod.stat == st and md.mod.value > 0 and "enemy" in md.receivers
                           and (not md.event or any(x > t for x in md.stacks)) for md in by_event + scoped_const))
        if parts[1] == "mark":   # while:mark:<element>: a Mark of that element is on the enemy
            return int(mark_up[int(parts[2])])
        if parts[1] == "squad":   # while:squad:<element>:<n>: at least n Trekkers of that element (EET) in the squad
            return int(elements.count(int(parts[2])) >= int(parts[3]))
        if parts[1] == "on_field":
            who = parts[2]
            idx = [i for i in range(n) if (who == "any" or (who == "support" and roles[i] == "support")
                                            or who == str(i))]
            return any(on_field_until[i] > t for i in idx)
        return False

    # ---- resilience bar
    en = team.enemy
    bar = (ResilienceBar(max=en.resilience, break_time=en.break_time, break_ratio=en.break_ratio,
                         lock_delay=en.lock_delay, lock_time=en.lock_time) if en.resilience > 0 and en.breaks else None)
    adjust = [toughness_adjust(gd, m.char_id) for m in team.members]
    resilience_by_member: dict = defaultdict(float)

    # ---- timeline
    dt = team.tick
    T = team.fight_length
    by_slot: dict = defaultdict(float)
    by_member: dict = defaultdict(float)
    first_cast: dict = {}
    queue: list = []   # (time, seq, member, HitSpec, action_name, cast_id)
    seq = [0]
    mark_up: dict = defaultdict(bool)      # element -> a Mark of that element is on the enemy
    next_mark: dict = defaultdict(float)   # element -> mark ICD end
    restart_gen: dict = defaultdict(int)   # proc / minion-schedule key -> current generation
    minion_uid = [0]
    proc_ready: dict = defaultdict(float)
    proc_expected: dict = {}   # (member, proc) -> ExpectedICD for chance procs
    proc_count: dict = defaultdict(int)
    followup_count: dict = defaultdict(int)
    main_event_followups = [(n, _norm_event(a.followup.event, 0), a.followup.every)
                            for n, a in members[0].actions.items() if a.followup and a.followup.event]
    main = members[0]
    busy_until = [1.0]          # main can't start a cast before this
    lock_until = [1.0]          # main can't auto before this
    pending: list = []          # (ready_time, action_name) for main followups / extra casts
    cancel_dodges: list = []    # times of the dodges that cancel an action into its followup
    auto_clock = [0.0]
    hit_cache: dict = {}

    for m in members:
        for name in m.actions:
            m.cd_ready[name] = 0.0
    main.cd_ready["skill"] = 1.0

    def get_hit(hid):
        if hid not in hit_cache:
            hit_cache[hid] = hit(gd, hid)
        return hit_cache[hid]

    last_hit: dict = {}   # (member, tag) -> time of that member's last hit with the tag

    def recent_ok(pattern: str, ev: str, t: float) -> bool:
        """`<event>&recent:<tag>:<seconds>`: the member that emitted the event also landed a <tag> hit
        within the last <seconds> (e.g. a minion hit counts only if its summoner dealt Skill DMG recently)."""
        if "&recent:" not in pattern:
            return True
        parts = ev.split(":")
        who = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        for alt in pattern.split("|"):
            base, _, cond = alt.partition("&recent:")
            if not _event_matches(base, ev):
                continue
            if not cond:
                return True
            tag, _, secs = cond.rpartition(":")
            last = last_hit.get((who, tag))
            if last is not None and t - last <= float(secs) + 1e-9:
                return True
        return False

    def once_ok(md: "_Mod", ev: str) -> bool:
        """`<event>&once`: that alternative activates the modifier only the first time it matches in the fight
        (e.g. "Dealing any DMG grants her Starender. Triggers once every 5 minutes"); other alternatives are free."""
        if "&once" not in md.event:
            return True
        for alt in md.event.split("|"):
            if not _event_matches(alt, ev):
                continue
            if "&once" not in alt:
                return True
            if alt not in md.once_used:
                md.once_used.add(alt)
                return True
        return False

    def while_ok(pattern: str, ev: str, t: float) -> bool:
        """`<event>&while:<condition>`: the alternative only counts while the condition holds
        (e.g. `cast:self:skill&while:status:berserk`: casting the skill while in Berserk)."""
        if "&while:" not in pattern:
            return True
        for alt in pattern.split("|"):
            if not _event_matches(alt, ev):
                continue
            conds = [c[len("while:"):] for c in alt.split("&")[1:] if c.startswith("while:")]
            if all(condition("while:" + c, t) for c in conds):
                return True
        return False

    emit_plans: dict = {}   # event -> what it can touch: emit is the hot path, and most events match very little

    def emit_plan(ev: str) -> tuple:
        def pool_listens(ms: MinionSpec) -> bool:
            return any(_event_matches(h.event, ev) for h in ms.reactions) or any(
                e and _event_matches(e, ev) for e in (ms.sacrifice_on, ms.resummon_on, ms.summon))

        plan_mods = []   # (mod, the event resets it, the event triggers it, it has &recent/&once/&while checks)
        for md in by_event:
            resets = any(_event_matches(_norm_event(r, md.owner), ev) for r in md.mod.trigger.reset_on or ())
            matches = _event_matches(md.event, ev)
            if resets or matches:
                plan_mods.append((md, resets, matches, "&" in md.event))
        plan_followups = [f for f in main_event_followups if _event_matches(f[1], ev)]
        plan_members = []
        for m in members:
            procs = [(pev, p) for pev, p in m.procs if _event_matches(pev, ev)]
            pools = [(pool, ms) for pool, ms in m.minions.items() if pool_listens(ms)]
            if procs or pools:
                plan_members.append((m, procs, pools))
        emit_plans[ev] = plan = (plan_mods, plan_followups, plan_members) if (
            plan_mods or plan_followups or plan_members) else ()
        return plan

    def emit(ev: str, t: float):
        plan = emit_plans.get(ev)
        if plan is None:
            plan = emit_plan(ev)
        if not plan:
            return
        plan_mods, plan_followups, plan_members = plan
        for md, resets, matches, checked in plan_mods:
            if resets and md.stacks:
                md.stacks = []
            if matches and (not checked or (recent_ok(md.event, ev, t) and once_ok(md, ev)
                                            and while_ok(md.event, ev, t))):
                trig = md.mod.trigger
                if trig.every > 1:
                    md.count += 1
                    if md.count % trig.every:
                        continue
                if t - md.last_trigger < trig.icd:
                    continue
                add = trig.add
                if trig.stacks_from:
                    add = status_stacks(trig.stacks_from, t)
                    if not add:
                        continue
                md.last_trigger = t
                dur = math.inf if (trig.duration == 0 or trig.duration == math.inf) else trig.duration
                md.stacks = [x for x in md.stacks if x > t]
                if refresh_stacks and md.stacks:
                    md.stacks = [t + dur] * len(md.stacks)
                md.stacks += [t + dur] * add
                if len(md.stacks) > trig.max_stacks:
                    md.stacks.sort()
                    md.stacks = md.stacks[-trig.max_stacks:]
        for fname, _, every in plan_followups:
            followup_count[fname] += 1
            if followup_count[fname] % every == 0:
                pending.append((max(t, lock_until[0]), fname, False))
        for m, procs, pools_ in plan_members:
            for _, p in procs:
                chancy = p.chance < 1
                if chancy or t >= proc_ready[(m.idx, p)]:
                    if p.when and not condition(p.when, t):
                        continue
                    if p.cost and any(m.resources[r] < c - 1e-9 for r, c in p.cost):
                        continue   # not enough of the resource: the proc doesn't fire (nothing is spent)
                    if p.summon and all(pool_blocked(m, pool) for pool in p.summon):
                        continue   # every pool it summons into is full and refuses new ones (at_max: block)
                    if p.every > 1:
                        proc_count[(m.idx, p)] += 1
                        if proc_count[(m.idx, p)] % p.every:
                            continue
                    mass = 1.0
                    if chancy:   # expected value: the proc's share of this event, with its ICD in expectation
                        eicd = proc_expected.get((m.idx, p))
                        if eicd is None:
                            eicd = proc_expected[(m.idx, p)] = ExpectedICD(p.chance, p.icd or 0.0)
                        mass = eicd.fire(t)
                        if mass <= 0:
                            continue
                    else:
                        proc_ready[(m.idx, p)] = t + (p.icd or 0.0)
                    if p.resilience:
                        amount = float(p.resilience) * mass * team.enemy.resilience
                        resilience_by_member[m.idx] += amount
                        if bar:
                            bar.damage(t, amount)
                    if p.energy:   # flat: Charge Efficiency applies to Energy from hits, not to this
                        m.energy += float(p.energy) * mass
                    for r, c in p.cost:
                        m.resources[r] -= c
                    for r, g in p.gain:
                        gain_resource(m, r, g * mass, t)
                    if chancy:
                        if not p.hit_id:
                            continue
                        p = replace(p, mult=p.mult * mass)
                    if p.restart:   # e.g. a refreshed DoT: the previous firing's pending ticks are dropped
                        key = f"rproc#{m.idx}#{id(p)}"
                        restart_gen[key] += 1
                        schedule(m, p, "proc", t, f"{key}#{restart_gen[key]}")
                    else:
                        schedule(m, p, "proc", t, f"proc#{seq[0]}")
            for pool, ms in pools_:
                for ri, h in enumerate(ms.reactions):   # each minion out reacts, with its own ICD
                    if not _event_matches(h.event, ev):
                        continue
                    for mn in list(alive[(m.idx, pool)]):
                        if t >= mn["ready"].get(ri, -1e9) - 1e-9:
                            mn["ready"][ri] = t + (h.icd or 0.0)
                            schedule(m, h, "minion_react", t, f"react#{mn['uid']}")
                if ms.sacrifice_on and _event_matches(ms.sacrifice_on, ev):
                    for mn in list(alive[(m.idx, pool)]):
                        vanish(m, pool, mn, t, sacrifice=True)
                if ms.resummon_on and _event_matches(ms.resummon_on, ev):
                    k = len(alive[(m.idx, pool)])
                    for mn in list(alive[(m.idx, pool)]):
                        vanish(m, pool, mn, t)
                    for _ in range(k):
                        summon(m, pool, t)
                if ms.summon and _event_matches(ms.summon, ev):
                    key = f"summon#{m.idx}#{pool}"
                    if ms.restart:
                        restart_gen[key] += 1
                    for k in range(ms.count):
                        seq[0] += 1
                        heapq.heappush(queue, (t + ms.offset + k * ms.every, seq[0], m.idx, None, "summon",
                                               f"{key}#{restart_gen[key]}"))

    def gain_resource(m: _Member, r: str, amount: float, t: float):
        """Add to a resource (capped); emits gain:<who>:<name> once per whole unit gained."""
        old = m.resources[r]
        new = min(m.res_max[r], old + amount)
        m.resources[r] = new
        for _ in range(int(math.floor(new + 1e-9) - math.floor(old + 1e-9))):
            emit(f"gain:{m.idx}:{r}", t)

    def pool_blocked(m: _Member, pool: str) -> bool:
        ms = m.minions.get(pool)
        return ms is None or (ms.at_max == "block" and len(alive[(m.idx, pool)]) >= ms.max)

    def summon(m: _Member, pool: str, t: float):
        ms = m.minions[pool]
        minion_uid[0] += 1
        mn = {"uid": minion_uid[0], "expire": t + ms.duration, "k": 0,
              "ready": {ri: t + (h.icd or 0.0) for ri, h in enumerate(ms.reactions)}}   # ICD starts at the summon
        alive[(m.idx, pool)].append(mn)
        if ms.attacks:
            seq[0] += 1
            heapq.heappush(queue, (t + ms.windup, seq[0], m.idx, None, "minion", f"{pool}#{mn['uid']}"))
        emit(f"summon:{m.idx}:{pool}", t)

    def vanish(m: _Member, pool: str, mn: dict, t: float, sacrifice: bool = False):
        lst = alive[(m.idx, pool)]
        if mn not in lst:
            return
        lst.remove(mn)
        emit(f"vanish:{m.idx}:{pool}", t)
        if sacrifice:
            emit(f"sacrifice:{m.idx}:{pool}", t)

    def summon_tick(m: _Member, pool: str, t: float):
        """One summon tick: a new minion, unless `max` are out: then the oldest is replaced or all are refreshed."""
        ms = m.minions[pool]
        lst = alive[(m.idx, pool)]
        emit(f"minion_tick:{m.idx}:{pool}", t)
        if len(lst) >= ms.max:
            if ms.at_max == "block":   # full: no new one (e.g. a turret limit)
                return
            if ms.at_max == "refresh":
                for mn in lst:
                    mn["expire"] = t + ms.duration
                return
            vanish(m, pool, lst[0], t)
        summon(m, pool, t)

    def schedule(m: _Member, h: HitSpec, action: str, t: float, cid: str, cut_at: float = math.inf):
        for k in range(h.count):
            if h.offset + k * h.interval > cut_at + 1e-9:   # a dodge-cancel drops the hits still to come
                break
            seq[0] += 1
            heapq.heappush(queue, (t + h.offset + k * h.interval, seq[0], m.idx, h, action, cid))

    def refill(m: _Member, name: str, t: float):
        q = m.recharge[name]
        while q and q[0] <= t + 1e-9:
            q.pop(0)
            m.charges[name] += 1

    def ready(m: _Member, name: str, t: float) -> bool:
        if name in m.max_charges:   # stored uses: recharged one at a time, UseInterval between uses
            refill(m, name, t)
            return m.charges[name] > 0 and t >= m.last_use[name] + m.use_interval[name] - 1e-9
        return t >= m.cd_ready[name] - 1e-9

    def give_charge(m: _Member, name: str, t: float):
        """A cooldown reset on a charged action: the use recharging now is ready; the rest move up."""
        q = m.recharge[name]
        if q:
            shift = q[0] - t
            q.pop(0)
            m.recharge[name] = [x - shift for x in q]
            m.charges[name] += 1

    def cooldown(m: _Member, name: str, start: float) -> float:
        """The cooldown of an action starting at `start`: a `cd_when` window scales it if it holds at that moment."""
        cd = m.cd.get(name, 0.0)
        for action, scale, when in m.cd_when:
            if action == name and condition(when, start):
                cd *= scale
        return cd

    def cast(m: _Member, name: str, t: float, from_cd: bool = True):
        a = m.actions[name]
        m.cast_count[name] += 1
        first_cast.setdefault((m.idx, name), round(t, 6))
        last_cast[(m.idx, name)] = t
        cid = f"{name}#{m.cast_count[name]}"
        c = m.cast_count[name]
        # A dodge-cancelled cast (the main loop handles autos) loses the hits after the dodge and ends early. The cancel
        # is the cast's own `dodge_cancel` or that of the followup it leads into.
        cancel = None
        if m.idx == 0 and team.assumptions.get("dodge_cancel", True):
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
            schedule(m, h, name, t, cid, cut_at)
        if from_cd and name in m.max_charges:
            refill(m, name, t)
            m.charges[name] -= 1
            m.last_use[name] = t
            q = m.recharge[name]
            cd = cooldown(m, name, t) - sum(cr["seconds"] * cr["times"] for cr in m.cd_reduce if cr["action"] == name)
            q.append(max(t, q[-1] if q else t) + cd)   # one recharge timer, progress kept across casts (user)
        elif from_cd:
            m.cd_ready[name] = t + a.cd_start + cooldown(m, name, t + a.cd_start)
            for cr in m.cd_reduce:
                if cr["action"] == name:
                    m.cd_ready[name] -= cr["seconds"] * cr["times"]
        if a.starts_cd and a.starts_cd in m.cd:
            start = t + min(lock, cut_at)   # user: a dodge starts it at once
            m.cd_ready[a.starts_cd] = start + cooldown(m, a.starts_cd, start)
        if name == "ult":
            m.energy = 0.0
        if name in m.kit.on_field:
            on_field_until[m.idx] = max(on_field_until[m.idx], t + m.kit.on_field[name])
        tgt = m.reset_cd.get(name)
        if tgt:
            if tgt in m.max_charges:
                give_charge(m, tgt, t)
            else:
                m.cd_ready[tgt] = t
        if m.idx == 0:
            lock_until[0] = max(lock_until[0], t + lock)
            busy_until[0] = t + min(DEFAULT_BUSY, lock) if lock else t
            if cancel:
                cancel_dodges.append(t + cut_at)
            if auto_clock[0] > 0:
                auto_loop[0] += 1
            auto_clock[0] = 0.0
            for _ in range(m.extra_casts.get(name, 0) if from_cd else 0):
                pending.append((t + DEFAULT_BUSY, name, True))
            for fname, fa in m.actions.items():
                if fa.followup and not fa.followup.event and fa.followup.after == name \
                        and m.cast_count[name] % fa.followup.every == 0:
                    pending.append((t + lock + fa.followup.delay, fname, False))
                    if not fa.followup.autos:   # no autos before the followup
                        lock_until[0] = max(lock_until[0], t + lock + fa.followup.delay)
        emit(f"cast:{m.idx}:{name}", t)

    stat_plans: dict = {}   # (receiver, minion, tags) -> (sheet with the constant mods folded in, by_event, while, [last key, last sheet])

    def stat_plan(receiver_block: StatBlock, receiver, tags_key: tuple, minion: bool) -> tuple:
        tags = set(tags_key)
        s = receiver_block.copy()

        def applies(md: _Mod) -> bool:
            return receiver in md.receivers and (not md.mod.hit_tags or bool(tags & set(md.mod.hit_tags)))
        for md in scoped_const:   # always on (snapshot) or averaged uptime (minion check)
            if applies(md) and (not minion or const_reaches_minions(md.mod)):
                s.add_stat(md.mod.stat, md.mod.value * md.constant, md.mod.is_pct)
        ok = (lambda md: reaches_minions(md.mod)) if minion else (lambda md: True)
        plan = (s, [md for md in by_event if applies(md) and ok(md)], [md for md in while_mods if applies(md) and ok(md)],
                [None, None])
        stat_plans[(receiver, minion, tags_key)] = plan
        return plan

    def stat_for(receiver_block: StatBlock, receiver, tags_key: tuple, t: float, minion: bool = False) -> StatBlock:
        """The receiver's sheet for a hit with these tags at time t. Which modifiers can apply depends only on
        (receiver, tags), so that part is planned once; `receiver_block` is fixed per (receiver, minion)."""
        plan = stat_plans.get((receiver, minion, tags_key)) or stat_plan(receiver_block, receiver, tags_key, minion)
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
            sig.append(condition(md.event, t))
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

    energy_used: dict = defaultdict(float)
    dmg_memo: dict = {}   # (hit id, level) -> (attacker sheet, enemy sheet, damage before the hit's own multiplier)
    has_charge_mods = any(md.mod.stat == CHARGE_EFF for md in mods)
    has_atk_spd = any(md.mod.stat == ATK_SPD and 0 in md.receivers for md in mods)

    def land(t: float, mi: int, h: HitSpec, action: str, cid: str):
        m = members[mi]
        for pool in h.summon:   # e.g. a proc that spends Resource Markers to put out a turret
            if pool in m.minions:
                summon_tick(m, pool, t)
        if h.hit_id == 0:   # marker: no damage, only emits marker:<who>:<tag> (and can inflict a Mark)
            for tag in h.tags:
                emit(f"marker:{mi}:{tag}", t)
            if h.applies_mark:   # e.g. Ann's wind wall "constantly inflicts" Breeze without dealing DMG
                el = elements[mi]
                was_up = mark_up[el]
                mark_up[el] = True
                emit(f"mark_applied:{mi}", t)
                emit(f"mark_refresh:{mi}" if was_up else f"mark_new:{mi}", t)
            return
        hd = get_hit(h.hit_id)
        tags_key = h.tags if type(h.tags) is tuple else tuple(h.tags)
        tags = set(tags_key)
        lv = hit_level(hd, m.skill_levels, m.pot_levels, fallback="auto" if action == "auto" else (
            "ult" if action == "ult" else "skill"))
        slot = slot_of(hd)
        minion = slot == "minion"
        attacker = stat_for(m.minion_static if minion else m.static, mi, tags_key, t, minion)
        taken = stat_for(enemy_static, "enemy", tags_key, t)
        # stat_for hands back the same sheets while no buff changed, and the hit's damage only depends on them.
        # Tests observe hits by patching `hit_damage`: a patched one is called for every hit.
        memo = dmg_memo.get((h.hit_id, lv)) if hit_damage is _HIT_DAMAGE else None
        if memo is not None and memo[0] is attacker and memo[1] is taken:
            raw = memo[2]
        else:
            # DEF reductions on the enemy (flat, then %) lower its DEF before defAmend (formula ref 2.def.c); floor 0
            defense = max(0.0, (team.enemy.defense + taken.flat[DEF]) * (1 + taken.pct[DEF]))
            e = Enemy(res=team.enemy.res, res_by_element=team.enemy.res_by_element,
                      defense=defense, broken=team.enemy.broken,
                      vul=team.enemy.vul, taken=taken)
            raw = hit_damage(hd, lv, attacker, e)
            dmg_memo[(h.hit_id, lv)] = (attacker, taken, raw)
        dmg_unbroken = raw * h.mult
        dmg = dmg_unbroken * (bar.ratio(t) if bar else 1.0)   # read before this hit lowers the bar
        res = dmg_unbroken * adjust[mi] * (1 + attacker.get(RES_BREAK_EFF))
        resilience_by_member[mi] += res
        if bar:
            bar.damage(t, res)
        by_slot[(mi, slot)] += dmg
        for tag in (*tags, f"{slot}_dmg"):
            last_hit[(mi, tag)] = t
        by_member[mi] += dmg
        # energy: main's hits charge the main; supports get a share
        if mi == 0 and hd.energy:
            key = cid
            cap = main.energy_cap.get(action, math.inf)
            gain = max(0.0, min(hd.energy, cap - energy_used[key]))
            energy_used[key] += gain
            for mm in members:
                eff = mm.charge + (stat_for(mm.static, mm.idx, (), t).get(CHARGE_EFF) if has_charge_mods else 0.0)
                mm.energy += gain * (1.0 if mm.idx == 0 else mm.kit.energy_conv) * eff
        el = elements[mi]   # Marks are per element: a Trekker applies and triggers Marks of their own element
        if h.applies_mark:
            was_up = mark_up[el]
            mark_up[el] = True
            emit(f"mark_applied:{mi}", t)
            emit(f"mark_refresh:{mi}" if was_up else f"mark_new:{mi}", t)
        triggers = h.triggers_mark or bool(tags & m.mark_tags)
        # Any member whose kit has a mark hit can trigger (consume) the Mark: supports like Shia compete with the main.
        if triggers and mark_up[el] and t >= next_mark[el] and m.kit.mark_hit:
            mark_up[el] = False
            next_mark[el] = t + team.mark_icd
            mh = HitSpec(hit_id=m.kit.mark_hit, tags=("mark",) + m.kit.mark_hit_tags)
            seq[0] += 1
            heapq.heappush(queue, (t, seq[0], mi, mh, "mark", "mark"))
            emit(f"mark:{mi}", t)
        for tag in tags:
            emit(f"hit:{mi}:{tag}", t)
        emit(f"hit:{mi}:{slot}_dmg", t)
        emit(f"damage:{mi}", t)   # once per landed hit, however many tags it has

    holds = {(int(h["member"]), h["action"]): (h["until"], float(h.get("max_wait", math.inf)), h.get("only_if", ""))
             for h in team.hold}
    hold_since: dict = {}

    def held(m: _Member, name: str, t: float) -> bool:
        """Team-file rotation timing: a ready action waits until `until` holds (at most `max_wait` s). With `only_if`,
        it only starts waiting if that holds when the action becomes ready (e.g. "wait if Cosette's skill shows <= 3 s")."""
        rule = holds.get((m.idx, name))
        if not rule:
            return False
        until, max_wait, only_if = rule
        if condition(until, t):
            hold_since.pop((m.idx, name), None)
            return False
        if (m.idx, name) not in hold_since and only_if and not condition(only_if, t):
            return False
        start = hold_since.setdefault((m.idx, name), t)
        if t - start >= max_wait:
            hold_since.pop((m.idx, name), None)
            return False
        return True

    steps = int(round(T / dt))
    auto = main.actions.get("auto")
    auto_hits = []   # (offset within the string, HitSpec with count 1)
    if auto and auto.duration > 0:
        for h in auto.hits:
            for k in range(h.count):
                auto_hits.append((h.offset + k * h.interval, HitSpec(**{**h.__dict__, "count": 1, "offset": 0.0})))
        auto_hits.sort(key=lambda x: x[0])
    auto_loop = [0]
    # Clock events: `timer:<s>` fires at 0, s, 2s, ... ("after the battle begins ... once every 20 s");
    # `dodge:0` is the main's dodge, one every `dodge_interval` s on average (assumption, default 10; see below);
    # `hit_taken:0` the main being hit, one every `hit_taken_interval` s.
    used = " ".join([md.event for md in by_event] + [pev for m in members for pev, _ in m.procs])
    timers = sorted({float(x) for x in re.findall(r"\btimer:(\d+(?:\.\d+)?)", used)})
    dodge_every = float(team.assumptions.get("dodge_interval", 10.0))
    spam = team.assumptions.get("dodge_spam")   # {interval: 3, potentials: [ids]}: dodge faster when the main has one
    if spam:
        owned = set(main.pot_levels) | {x.potential_id for (j, x) in extra if j == 0 and isinstance(x, ResolvedPotential)}
        want = set(spam.get("potentials") or [])
        if not want or owned & want:
            dodge_every = float(spam["interval"])
    dodge_time = float(team.assumptions.get("dodge_time", 10 / 30))   # user: a dodge costs 10 frames of attacking
    next_dodge = [dodge_every]
    # Dodge-cancel (Nanoha): dodging at the end of each auto string shortens it, so the main dodges every string and
    # those dodges replace the periodic ones (user, 2026-11-04).
    cancel_at = auto.dodge_at if (auto and auto.dodge_at is not None
                                  and team.assumptions.get("dodge_cancel", True)) else None
    auto_len = auto.dodge_duration if cancel_at is not None else (auto.duration if auto else 0.0)
    if cancel_at is not None:
        dodge_every = 0.0
    hit_every = float(team.assumptions.get("hit_taken_interval", 20.0))   # `hit_taken:0`: the main is hit (user: ~20 s)
    # A status name that is a plain name and not also a minion pool is up exactly when its own mod has a live stack.
    named_plain = [(name, md) for name, md in named.items() if not ("+" in name or ">=" in name or name in pools)]
    named_other = [name for name in named if "+" in name or ">=" in name or name in pools]
    cast_order = members[1:] + [main]
    for step in range(steps + 1):
        t = step * dt
        for per in timers:
            if per > 0 and abs(t / per - round(t / per)) * per < dt / 2:
                emit(f"timer:{per:g}", t)
        # A dodge cancelling an action (Amber) is free and takes the place of the next periodic one.
        while cancel_dodges and t >= cancel_dodges[0] - 1e-9:
            cancel_dodges.pop(0)
            emit("dodge:0", t)
            next_dodge[0] += dodge_every
        # Dodges need control: one due during a cast's lock (no control, but immune) waits for the lock to end.
        # The schedule keeps its average rate (user: the 1 per 10 s came from real fights, locks included), but two
        # dodges are at least DODGE_CD apart. Each pauses the auto string for `dodge_time`.
        if dodge_every > 0 and t >= next_dodge[0] - 1e-9 and t >= lock_until[0] - 1e-9:
            lock_until[0] = max(lock_until[0], t + dodge_time)   # first, so a follow-up waits for the dodge to end
            emit("dodge:0", t)
            next_dodge[0] = max(next_dodge[0] + dodge_every, t + min(DODGE_CD, dodge_every))
        if hit_every > 0 and t > 0 and abs(t / hit_every - round(t / hit_every)) * hit_every < dt / 2 \
                and not (bar is not None and bar.broken(t)):   # a broken boss doesn't attack (user)
            emit("hit_taken:0", t)
        for m in members:
            m.energy += m.kit.energy_per_second * dt
            if on_field_until[m.idx] > t:
                before = on_field_time[m.idx]
                on_field_time[m.idx] += dt
                if int((on_field_time[m.idx] + 1e-9) // 5.0) > int((before + 1e-9) // 5.0):
                    emit(f"on_field_5s:{m.idx}", t)   # "every 5 s they are on the field"
                if int(on_field_time[m.idx] + 1e-9) > int(before + 1e-9):
                    emit(f"on_field_1s:{m.idx}", t)   # every second on the field
        for name, md in named_plain:
            st = md.stacks
            if st and (st[-1] > t or max(st) > t):
                status_time[name] += dt
        for name in named_other:
            if status_stacks(name, t) > 0:
                status_time[name] += dt
        for pool in pools:
            if status_stacks(pool, t) > 0:
                status_time[pool] += dt
        for (mi, pool), lst in list(alive.items()):   # minion lifetimes
            for mn in [x for x in lst if x["expire"] <= t + 1e-9]:
                vanish(members[mi], pool, mn, t)
        # supports first, then main
        for m in cast_order:
            is_main = m.idx == 0
            if is_main and t < busy_until[0] - 1e-9:
                continue
            if not is_main and m.kit.wait_on_field and on_field_until[m.idx] > t + 1e-9:
                continue
            if is_main and pending:
                pending.sort()
                if pending[0][0] <= t + 1e-9:
                    _, name, _ = pending.pop(0)
                    cast(m, name, t, from_cd=False)
                    continue
            if "ult" in m.actions and m.ult_cost and m.energy >= m.ult_cost and ready(m, "ult", t) \
                    and not held(m, "ult", t):
                cast(m, "ult", t)
                continue
            if "skill" in m.actions and ready(m, "skill", t):
                if is_main and t < 1.0 - 1e-9:
                    continue
                if held(m, "skill", t):
                    continue
                cast(m, "skill", t)
        # main autos: a string that restarts after every cast
        if auto_hits and t >= lock_until[0] - 1e-9:
            # ATK SPD runs the whole string faster, shots and reload (user-timed shots; the reload is a GUESS).
            speed = 1.0 + (stat_for(main.static, 0, (), t).get(ATK_SPD) if has_atk_spd else 0.0)
            c0, c1 = auto_clock[0], auto_clock[0] + dt * speed
            for off, h in auto_hits:
                if c0 - 1e-9 <= off < c1 - 1e-9:
                    seq[0] += 1
                    heapq.heappush(queue, (t, seq[0], 0, h, "auto", f"auto#{auto_loop[0]}#{h.hit_id}"))
            if cancel_at is not None and c0 - 1e-9 <= cancel_at < c1 - 1e-9:
                emit("dodge:0", t)
            if c1 >= auto_len - 1e-9:
                c1 = 0.0
                auto_loop[0] += 1
                main.cast_count["auto"] += 1
            auto_clock[0] = c1
        while queue and queue[0][0] <= t + 1e-9:
            ht, _, mi, h, action, cid = heapq.heappop(queue)
            if ht > T:
                continue
            if cid.startswith(("rproc#", "summon#")):
                key, _, gen = cid.rpartition("#")
                if int(gen) != restart_gen[key]:
                    continue   # superseded by a newer firing / schedule
            if action == "summon":
                summon_tick(members[mi], cid.split("#")[2], ht)
                continue
            if action == "minion":
                pool, _, uid = cid.partition("#")
                m = members[mi]
                mn = next((x for x in alive[(mi, pool)] if x["uid"] == int(uid)), None)
                if mn is None or mn["expire"] < ht - 1e-9:
                    continue
                ms = m.minions[pool]
                h = ms.attacks[mn["k"] % len(ms.attacks)]
                mn["k"] += 1
                seq[0] += 1
                heapq.heappush(queue, (ht + ms.interval / (1.0 + ms.speed), seq[0], mi, None, "minion", cid))
                for k in range(h.count):
                    land(ht + k * h.interval, mi, h, "minion", cid)
                continue
            land(ht, mi, h, action, cid)

    casts = {(m.idx, a): c for m in members for a, c in m.cast_count.items()}
    for m in members:
        for a in m.actions:
            casts.setdefault((m.idx, a), 0)
    return SimResult(total=sum(by_member.values()), by_member=dict(by_member), by_slot=dict(by_slot),
                     casts=casts, first_cast=first_cast, unknown_modifiers=sorted(unknown),
                     on_field_time=dict(enumerate(on_field_time)), status_time=dict(status_time),
                     breaks=list(bar.breaks) if bar else [], broken_time=bar.broken_time(T) if bar else 0.0,
                     resilience_by_member=dict(resilience_by_member))
