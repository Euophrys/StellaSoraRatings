"""Tick-based 120 s fight simulation producing total team damage."""
from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass, field

from .data import GameData
from .effects import Modifier, disc_modifiers
from .formula import Enemy, hit_damage, slot_of
from .game import char_base_stats, disc_base_stats, hit, hit_level, skill_cd, ult_energy
from .kit import ActionSpec, HitSpec, ResolvedPotential, resolve_buffs, resolve_potential
from .stats import StatBlock
from .team import FILLER, FILLER_SOURCE_DISC, Build, EmblemLine, EmblemSkillLevel, TeamConfig

DEFAULT_BUSY = 1.5   # GUESS: seconds after a main cast before another cast can start (animation)


@dataclass
class SimResult:
    total: float
    by_member: dict[int, float]
    by_slot: dict[tuple[int, str], float]
    casts: dict[tuple[int, str], int]
    first_cast: dict[tuple[int, str], float]
    unknown_modifiers: list[str]


# ---------------------------------------------------------------- caches

_POT_CACHE: dict = {}
_DISC_CACHE: dict = {}


def _potential(gd, kit, pid, lv) -> ResolvedPotential:
    key = (id(gd), kit.char_id, kit.role, pid, lv)
    if key not in _POT_CACHE:
        _POT_CACHE[key] = resolve_potential(gd, kit, pid, lv)
    return _POT_CACHE[key]


def _disc_stats(gd, disc_id, copies) -> StatBlock:
    key = ("stats", id(gd), disc_id, copies)
    if key not in _DISC_CACHE:
        _DISC_CACHE[key] = disc_base_stats(gd, FILLER_SOURCE_DISC, copies=6) if disc_id == FILLER \
            else disc_base_stats(gd, disc_id, copies=copies)
    return _DISC_CACHE[key]


def _disc_mods(gd, disc_id, copies) -> list[Modifier]:
    if disc_id == FILLER:
        return []
    key = ("mods", id(gd), disc_id, copies)
    if key not in _DISC_CACHE:
        _DISC_CACHE[key] = disc_modifiers(gd, disc_id, copies)[0]
    return _DISC_CACHE[key]


# ---------------------------------------------------------------- helpers

def _norm_event(ev: str, owner: int) -> str:
    parts = ev.split(":")
    if len(parts) >= 2:
        parts[1] = {"self": str(owner), "main": "0"}.get(parts[1], parts[1])
    return ":".join(parts)


def _event_matches(pattern: str, ev: str) -> bool:
    p, e = pattern.split(":"), ev.split(":")
    if len(p) != len(e):
        return False
    return all(a == b or a == "any" for a, b in zip(p, e))


def _targets(target: str, owner: int, n: int) -> list[int | str]:
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
    static: StatBlock = None
    cd_ready: dict = field(default_factory=dict)
    cd: dict = field(default_factory=dict)
    energy: float = 0.0
    ult_cost: float = 0.0
    energy_cap: dict = field(default_factory=dict)
    cast_count: dict = field(default_factory=lambda: defaultdict(int))


def simulate(gd: GameData, team: TeamConfig, build: Build, emblems: bool = True,
             discs: tuple[list, list] | None = None, extra: list | None = None) -> SimResult:
    """Simulate one fight.

    discs: (main_slots, support_slots) as [(disc_id, copies)], default the team's lineup.
    extra: [(member_idx, Modifier | EmblemLine | EmblemSkillLevel | ResolvedPotential)] for rating.
    """
    n = len(team.members)
    extra = extra or []
    discs_main, discs_support = discs if discs is not None else (team.discs_main, team.discs_support)
    unknown: set[str] = set()
    uptime_default = float(team.assumptions.get("unknown_trigger_uptime", 1.0))
    disc_team = team.assumptions.get("disc_stats_target", "team") == "team"

    # ---- per-member setup: potentials, actions, levels
    members: list[_Member] = []
    mods: list[_Mod] = []

    def add_mod(m: Modifier, owner: int, src_target: str | None = None):
        tgt = src_target or m.target
        rec = _targets(tgt, owner, n)
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
        mods.append(_Mod(m, owner, rec, event=_norm_event(t.event, owner)))

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
        resolved = [_potential(gd, kit, p, lv) for p, lv in pot_levels.items()]
        resolved += [x for (j, x) in extra if j == i and isinstance(x, ResolvedPotential)]
        owned = set(pot_levels)

        def keep(h: HitSpec) -> bool:
            return (not h.requires or any(r in owned for r in h.requires)) and not any(e in owned for e in h.excludes)

        actions: dict[str, ActionSpec] = {}
        for name, a in kit.actions.items():
            actions[name] = ActionSpec(a.name, list(a.hits), a.lock, a.duration, a.skill_id, a.followup)
        for rp in resolved:
            for name, a in rp.add_actions.items():
                actions[name] = ActionSpec(a.name, list(a.hits), a.lock, a.duration, a.skill_id, a.followup)
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

        m = _Member(
            idx=i, cfg=mc, kit=kit, actions=actions, skill_levels=levels, pot_levels=pot_levels,
            mark_tags={t for rp in resolved for t in rp.mark_tags},
            extra_casts={k: v for rp in resolved for k, v in rp.extra_casts.items()},
            reset_cd={**kit.reset_cd, **{k: v for rp in resolved for k, v in rp.reset_cd.items()}},
            cd_reduce=[rp.cd_reduce for rp in resolved if rp.cd_reduce],
            procs=[(_norm_event(p.event, i), p) for rp in resolved for p in rp.procs if keep(p)],
        )
        for name, a in actions.items():
            if a.skill_id:
                m.cd[name] = skill_cd(gd, a.skill_id)
                sk = gd.table("Skill").get(str(a.skill_id), {})
                if sk.get("GetEnergyLimit"):
                    m.energy_cap[name] = sk["GetEnergyLimit"] / 10000
        if "ult" in actions and actions["ult"].skill_id:
            m.ult_cost = ult_energy(gd, actions["ult"].skill_id)
        members.append(m)

        for rp in resolved:
            for md in rp.modifiers:
                add_mod(md, i)
        for md in resolve_buffs(gd, kit, levels):
            add_mod(md, i)
        for (j, x) in extra:
            if j == i and isinstance(x, Modifier):
                add_mod(x, i)

    # ---- static stats: base + discs + emblems
    disc_stats = StatBlock()
    for d, c in list(discs_main) + list(discs_support):
        disc_stats.add(_disc_stats(gd, d, c))
    for d, c in discs_main:
        for md in _disc_mods(gd, d, c):
            add_mod(md, 0, "team" if (disc_team and md.target == "self") else None)
    for i, m in enumerate(members):
        s = char_base_stats(gd, m.cfg.char_id)
        if disc_team or i == 0:
            s.add(disc_stats)
        lines = list(m.cfg.emblems) if emblems else []
        lines += [x for (j, x) in extra if j == i and isinstance(x, EmblemLine)]
        for e in lines:
            if isinstance(e, EmblemLine):
                s.add_stat(e.stat, e.value, e.is_pct)
        m.static = s
    enemy_static = team.enemy.taken.copy()

    # Fold unscoped always-on mods into static blocks.
    dynamic: list[_Mod] = []
    for md in mods:
        if md.event == "" and not md.mod.hit_tags:
            for r in md.receivers:
                blk = enemy_static if r == "enemy" else members[r].static
                blk.add_stat(md.mod.stat, md.mod.value * md.constant, md.mod.is_pct)
        else:
            dynamic.append(md)
    for md in dynamic:
        if md.mod.needs_scope and not md.mod.hit_tags:
            unknown.add(f"{md.mod.source}: {md.mod.label()} applied to all hits (scope unknown)")
    for md in mods:
        if md.event == "" and md.mod.needs_scope and not md.mod.hit_tags:
            unknown.add(f"{md.mod.source}: {md.mod.label()} applied to all hits (scope unknown)")

    by_event: list[_Mod] = [md for md in dynamic if md.event]
    scoped_const: list[_Mod] = [md for md in dynamic if not md.event]

    # ---- timeline
    dt = team.tick
    T = team.fight_length
    by_slot: dict = defaultdict(float)
    by_member: dict = defaultdict(float)
    first_cast: dict = {}
    queue: list = []   # (time, seq, member, HitSpec, action_name, cast_id)
    seq = [0]
    mark_up = [False]
    next_mark = [0.0]
    proc_ready: dict = defaultdict(float)
    main = members[0]
    busy_until = [1.0]          # main can't start a cast before this
    lock_until = [1.0]          # main can't auto before this
    pending: list = []          # (ready_time, action_name) for main followups / extra casts
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

    def emit(ev: str, t: float):
        for md in by_event:
            if _event_matches(md.event, ev):
                trig = md.mod.trigger
                if t - md.last_trigger < trig.icd:
                    continue
                md.last_trigger = t
                dur = math.inf if (trig.duration == 0 or trig.duration == math.inf) else trig.duration
                md.stacks = [x for x in md.stacks if x > t]
                md.stacks.append(t + dur)
                if len(md.stacks) > trig.max_stacks:
                    md.stacks.sort()
                    md.stacks = md.stacks[-trig.max_stacks:]
        for m in members:
            for pev, p in m.procs:
                if _event_matches(pev, ev) and t >= proc_ready[(m.idx, p)]:
                    proc_ready[(m.idx, p)] = t + (p.icd or 0.0)
                    schedule(m, p, "proc", t, f"proc#{seq[0]}")

    def schedule(m: _Member, h: HitSpec, action: str, t: float, cid: str):
        for k in range(h.count):
            seq[0] += 1
            heapq.heappush(queue, (t + h.offset + k * h.interval, seq[0], m.idx, h, action, cid))

    def cast(m: _Member, name: str, t: float, from_cd: bool = True):
        a = m.actions[name]
        m.cast_count[name] += 1
        first_cast.setdefault((m.idx, name), round(t, 6))
        cid = f"{name}#{m.cast_count[name]}"
        for h in a.hits:
            schedule(m, h, name, t, cid)
        if from_cd:
            m.cd_ready[name] = t + m.cd.get(name, 0.0)
            for cr in m.cd_reduce:
                if cr["action"] == name:
                    m.cd_ready[name] -= cr["seconds"] * cr["times"]
        if name == "ult":
            m.energy = 0.0
        tgt = m.reset_cd.get(name)
        if tgt:
            m.cd_ready[tgt] = t
        if m.idx == 0:
            lock_until[0] = max(lock_until[0], t + a.lock)
            busy_until[0] = t + min(DEFAULT_BUSY, a.lock) if a.lock else t
            if auto_clock[0] > 0:
                auto_loop[0] += 1
            auto_clock[0] = 0.0
            for _ in range(m.extra_casts.get(name, 0) if from_cd else 0):
                pending.append((t + DEFAULT_BUSY, name, True))
            for fname, fa in m.actions.items():
                if fa.followup and fa.followup.after == name and m.cast_count[name] % fa.followup.every == 0:
                    pending.append((t + a.lock, fname, False))
        emit(f"cast:{m.idx}:{name}", t)

    def stat_for(receiver_block: StatBlock, receiver, tags: set, t: float) -> StatBlock:
        s = receiver_block.copy()
        for md in scoped_const:
            if receiver in md.receivers and (not md.mod.hit_tags or tags & set(md.mod.hit_tags)):
                s.add_stat(md.mod.stat, md.mod.value * md.constant, md.mod.is_pct)
        for md in by_event:
            if md.stacks and receiver in md.receivers and (not md.mod.hit_tags or tags & set(md.mod.hit_tags)):
                k = sum(1 for x in md.stacks if x > t)
                if k:
                    s.add_stat(md.mod.stat, md.mod.value * k, md.mod.is_pct)
        return s

    energy_used: dict = defaultdict(float)

    def land(t: float, mi: int, h: HitSpec, action: str, cid: str):
        m = members[mi]
        hd = get_hit(h.hit_id)
        tags = set(h.tags)
        lv = hit_level(hd, m.skill_levels, m.pot_levels, fallback="auto" if action == "auto" else (
            "ult" if action == "ult" else "skill"))
        attacker = stat_for(m.static, mi, tags, t)
        taken = stat_for(enemy_static, "enemy", tags, t)
        e = Enemy(res=team.enemy.res, defense=team.enemy.defense, broken=team.enemy.broken,
                  vul=team.enemy.vul, taken=taken)
        dmg = hit_damage(hd, lv, attacker, e)
        slot = slot_of(hd)
        by_slot[(mi, slot)] += dmg
        by_member[mi] += dmg
        # energy: main's hits charge the main; supports get a share
        if mi == 0 and hd.energy:
            key = cid
            cap = main.energy_cap.get(action, math.inf)
            gain = max(0.0, min(hd.energy, cap - energy_used[key]))
            energy_used[key] += gain
            for mm in members:
                mm.energy += gain * (1.0 if mm.idx == 0 else mm.kit.energy_conv)
        if h.applies_mark:
            mark_up[0] = True
        triggers = h.triggers_mark or bool(tags & m.mark_tags)
        if mi == 0 and triggers and mark_up[0] and t >= next_mark[0] and m.kit.mark_hit:
            mark_up[0] = False
            next_mark[0] = t + team.mark_icd
            mh = HitSpec(hit_id=m.kit.mark_hit, tags=("mark",))
            seq[0] += 1
            heapq.heappush(queue, (t, seq[0], 0, mh, "mark", "mark"))
            emit("mark:0", t)
        for tag in tags:
            emit(f"hit:{mi}:{tag}", t)
        emit(f"hit:{mi}:{slot}_dmg", t)

    steps = int(round(T / dt))
    auto = main.actions.get("auto")
    auto_hits = []   # (offset within the string, HitSpec with count 1)
    if auto and auto.duration > 0:
        for h in auto.hits:
            for k in range(h.count):
                auto_hits.append((h.offset + k * h.interval, HitSpec(**{**h.__dict__, "count": 1, "offset": 0.0})))
        auto_hits.sort(key=lambda x: x[0])
    auto_loop = [0]
    for step in range(steps + 1):
        t = step * dt
        for m in members:
            m.energy += m.kit.energy_per_second * dt
        # supports first, then main
        for m in members[1:] + [main]:
            is_main = m.idx == 0
            if is_main and t < busy_until[0] - 1e-9:
                continue
            if is_main and pending:
                pending.sort()
                if pending[0][0] <= t + 1e-9:
                    _, name, _ = pending.pop(0)
                    cast(m, name, t, from_cd=False)
                    continue
            if "ult" in m.actions and m.ult_cost and m.energy >= m.ult_cost and t >= m.cd_ready["ult"] - 1e-9:
                cast(m, "ult", t)
                continue
            if "skill" in m.actions and t >= m.cd_ready["skill"] - 1e-9:
                if is_main and t < 1.0 - 1e-9:
                    continue
                cast(m, "skill", t)
        # main autos: a string that restarts after every cast
        if auto_hits and t >= lock_until[0] - 1e-9:
            c0, c1 = auto_clock[0], auto_clock[0] + dt
            for off, h in auto_hits:
                if c0 - 1e-9 <= off < c1 - 1e-9:
                    seq[0] += 1
                    heapq.heappush(queue, (t, seq[0], 0, h, "auto", f"auto#{auto_loop[0]}#{h.hit_id}"))
            if c1 >= auto.duration - 1e-9:
                c1 = 0.0
                auto_loop[0] += 1
                main.cast_count["auto"] += 1
            auto_clock[0] = c1
        while queue and queue[0][0] <= t + 1e-9:
            ht, _, mi, h, action, cid = heapq.heappop(queue)
            if ht > T:
                continue
            land(ht, mi, h, action, cid)

    casts = {(m.idx, a): c for m in members for a, c in m.cast_count.items()}
    for m in members:
        for a in m.actions:
            casts.setdefault((m.idx, a), 0)
    return SimResult(total=sum(by_member.values()), by_member=dict(by_member), by_slot=dict(by_slot),
                     casts=casts, first_cast=first_cast, unknown_modifiers=sorted(unknown))
