"""Per-Trekker kit specs (YAML): hit counts, timing, marks, potential behaviour."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from .data import GameData, REPO_ROOT
from .effects import Modifier, Trigger, potential_modifiers, _interpret
from .game import potential_pools, skill_ids
from .refs import level_row, resolve

SPECS = REPO_ROOT / "specs" / "trekkers"

DEFAULT_LOCKS = {"auto": 0.0, "skill": 3.0, "ult": 5.0}
DEFAULT_ON_FIELD = {"skill": 4.0, "ult": 4.0}   # GUESS: a support appears to cast, then leaves


@dataclass(frozen=True)
class HitSpec:
    hit_id: int
    count: int = 1
    offset: float = 0.0
    interval: float = 0.1
    tags: tuple[str, ...] = ()
    triggers_mark: bool = False
    applies_mark: bool = False
    requires: tuple[int, ...] = ()
    excludes: tuple[int, ...] = ()
    requires_all: tuple[int, ...] = ()   # lands only if all of these potentials are in the build
    mult: float = 1.0      # damage multiplier on the hit (e.g. a Mirror Image with 50% of the DMG Multiplier)
    cycle: tuple[int, ...] = ()   # (n, i): lands only on the i-th of every n casts of its action (1-based)
    from_cast: int = 0     # lands only from the Nth cast of its action on
    upto_cast: int = 0     # lands only up to the Nth cast of its action
    # procs only
    event: str = ""
    icd: float = 0.0
    every: object = 1      # fire on every Nth matching event (number or {ref: ...})
    when: str = ""         # only fires while this condition holds, e.g. "while:status:butterfly"
    restart: bool = False  # a new firing cancels this proc's hits still pending (a refreshed DoT)
    chance: float = 1.0    # probability per matching event (expected value; `icd` is then an expected-value ICD)
    resilience: object = 0.0   # fraction of the enemy's max resilience bar removed per proc (number or {param/ref})
    energy: object = 0.0       # Energy granted to the proc's owner per proc (number or {param/ref})
    gain: tuple = ()       # ((resource, amount), ...): the proc adds to its owner's resources (kit `resources:`)
    cost: tuple = ()       # ((resource, amount), ...): the proc only fires if the owner has that much, and spends it
    summon: tuple = ()     # minion pools: the hit summons one into each when it lands (a summon tick)


@dataclass
class Followup:
    after: str = ""        # cast after every Nth cast of this action, once its lock ends
    every: object = 1      # N: a number, or {ref: ...} resolved per potential level
    event: str = ""        # or: cast after every Nth matching event (e.g. "hit:self:glow")
    delay: float = 0.0     # seconds after `after`'s lock ends before it's cast (input / animation gap)
    autos: bool = False    # the main auto attacks during the delay
    dodge_at: float | None = None   # the main dodge-cancels `after` at this offset from its cast, cutting later hits ...
    dodge_duration: float = 0.0     # ... and this is cast this long after it (team assumption dodge_cancel, default on)


@dataclass
class ActionSpec:
    name: str
    hits: list[HitSpec]
    lock: float = 0.0
    duration: float = 0.0
    skill_id: int | None = None
    followup: Followup | None = None
    starts_cd: str = ""    # casting this (re)starts that action's cooldown from the end of this one's lock
    cd_start: float = 0.0  # this action's own cooldown starts this many seconds after its cast
    charges: int = 0       # uses that can be stored (0 = Skill.SectionAmount from data, else 1)
    use_interval: float | None = None   # min seconds between uses of stored charges (None = Skill.UseInterval)
    dodge_at: float | None = None   # the main dodge-cancels this action at this offset (auto: the string's recovery; cast: cuts later hits) ...
    dodge_duration: float = 0.0     # ... and it then lasts this long (team assumption dodge_cancel, default on)


@dataclass
class MinionSpec:
    """A pool of summoned minions with their own lifetimes and attack loops (e.g. Mistique's Pumpka Phantoms)."""
    name: str
    summon: str = ""           # event that starts a summon schedule, e.g. "cast:self:skill"
    offset: float = 0.0        # first summon tick after the event
    every: float = 3.0         # seconds between summon ticks
    count: int = 1             # summon ticks per schedule
    restart: bool = True       # a new schedule cancels the ticks still pending from the previous one
    max: int = 1               # minions out at once
    duration: float = math.inf  # each minion's lifetime from its summon
    at_max: str = "replace"    # a tick with `max` out: "replace" (the oldest vanishes) | "refresh" (all lifetimes reset)
    windup: float = 0.0        # first attack after the summon
    interval: float = 1.0      # seconds between attacks
    attacks: list = field(default_factory=list)   # HitSpecs, cycled
    sacrifice_on: str = ""     # event: all minions are sacrificed (vanish)
    resummon_on: str = ""      # event: all minions vanish and as many are summoned again
    speed: float = 0.0         # ATK SPD: attack interval / (1 + speed)
    reactions: list = field(default_factory=list)   # HitSpecs with `event` / `icd`: each minion attacks on the event,
                                                    # with its own ICD that starts on cooldown at its summon


@dataclass
class ModifierOverride:
    index: int | None = None
    stat: int | None = None
    set: dict = field(default_factory=dict)


@dataclass
class PotentialSpec:
    add_hits: dict[str, list[HitSpec]] = field(default_factory=dict)
    replace_hits: dict[str, list[HitSpec]] = field(default_factory=dict)
    add_actions: dict[str, ActionSpec] = field(default_factory=dict)
    overrides: list[ModifierOverride] = field(default_factory=list)
    mark_tags: tuple[str, ...] = ()
    extra_casts: dict[str, int] = field(default_factory=dict)
    reset_cd: dict[str, str] = field(default_factory=dict)
    cd_reduce: dict | None = None
    procs: list[HitSpec] = field(default_factory=list)
    add_charges: dict[str, int] = field(default_factory=dict)   # {action: N} more stored uses
    cd_scale: dict[str, float] = field(default_factory=dict)    # {action: x} cooldown multiplied by x
    cd_when: list[dict] = field(default_factory=list)   # [{action, scale, when}]: a cooldown starting while `when` holds is scaled
    minion_rules: dict[str, dict] = field(default_factory=dict)  # {pool: {MinionSpec field: value}}
    ult_cost_scale: float = 1.0   # the ult's Energy cost is multiplied by this
    note: str = ""


@dataclass
class BuffSpec:
    effect: int | None    # Effect id, leveled by `level` (or None when `attribute` is used)
    level: str            # which skill's level picks the effect/attribute row
    event: str
    duration: object = "inf"   # number, "inf" or {ref: ...}
    target: str = "self"
    max_stacks: object = 1     # number or {ref: ...}
    attribute: int | None = None   # OnceAdditionalAttribute id instead of an effect
    as_stat: int | None = None
    hit_tags: tuple = ()
    per_stack: bool = False
    name: str = ""
    add: object = 1            # stacks added per event
    requires: tuple = ()       # only with any of these potentials
    excludes: tuple = ()       # not with any of these potentials
    requires_all: tuple = ()   # only with all of these potentials
    minions: bool = False      # also reaches the owner's minions
    every: object = 1          # activate on every Nth event
    icd: object = 0.0          # seconds between activations
    reset_on: tuple = ()       # events that clear all stacks


@dataclass
class TalentSpec:
    """A key talent (Talent Type 1, unlocked by a dupe): its behaviour isn't in data."""
    buffs: list[BuffSpec] = field(default_factory=list)
    buff_events: dict[str, str] = field(default_factory=dict)   # named base buff -> extra event alternative
    note: str = ""


@dataclass
class Kit:
    char_id: int
    role: str
    actions: dict[str, ActionSpec]
    mark_hit: int | None = None
    mark_hit_tags: tuple[str, ...] = ()   # extra tags on the Mark hit (e.g. Noya's Cyclone), for "a Mark that inflicts X"
    energy_per_second: float = 0.0
    energy_conv: float = 1.0
    potentials: dict[int, PotentialSpec] = field(default_factory=dict)
    buffs: list[BuffSpec] = field(default_factory=list)
    reset_cd: dict[str, str] = field(default_factory=dict)
    on_field: dict[str, float] = field(default_factory=dict)   # support: seconds on the battlefield per cast
    talents: dict[int, TalentSpec] = field(default_factory=dict)
    minions: dict[str, MinionSpec] = field(default_factory=dict)
    procs: list[HitSpec] = field(default_factory=list)   # base-kit procs (e.g. a DoT after each Mark trigger)
    wait_on_field: bool = False   # support: no new cast while still on the field (an ult would cancel the skill)
    ult_only_with: tuple[int, ...] = ()   # the ult is only used in a squad with one of these Trekkers (char ids)
    resources: dict[str, float] = field(default_factory=dict)   # name -> most that can be held (e.g. Resource Markers)


@dataclass
class ResolvedPotential:
    potential_id: int
    level: int
    modifiers: list[Modifier]
    notes: list[str]
    add_hits: dict[str, list[HitSpec]]
    replace_hits: dict[str, list[HitSpec]]
    add_actions: dict[str, ActionSpec]
    mark_tags: tuple[str, ...]
    extra_casts: dict[str, int]
    reset_cd: dict[str, str]
    cd_reduce: dict | None
    procs: list[HitSpec]
    add_charges: dict[str, int] = field(default_factory=dict)
    cd_scale: dict[str, float] = field(default_factory=dict)
    minion_rules: dict[str, dict] = field(default_factory=dict)
    cd_when: list[dict] = field(default_factory=list)
    ult_cost_scale: float = 1.0


def _hitspec(d: dict) -> HitSpec:
    return HitSpec(
        hit_id=int(d["hit"]), count=int(d.get("count", 1)), offset=float(d.get("offset", 0.0)),
        interval=float(d.get("interval", 0.1)), tags=tuple(d.get("tags", ())),
        triggers_mark=bool(d.get("triggers_mark", False)), applies_mark=bool(d.get("applies_mark", False)),
        requires=tuple(int(x) for x in d.get("requires", ())), excludes=tuple(int(x) for x in d.get("excludes", ())),
        requires_all=tuple(int(x) for x in d.get("requires_all", ())), mult=float(d.get("mult", 1.0)),
        cycle=tuple(int(x) for x in d.get("cycle", ())), from_cast=int(d.get("from_cast", 0)),
        upto_cast=int(d.get("upto_cast", 0)),
        event=str(d.get("event", "")), icd=d.get("icd", 0.0), every=d.get("every", 1), when=str(d.get("when", "")),
        restart=bool(d.get("restart", False)), chance=float(d.get("chance", 1.0)), resilience=d.get("resilience", 0.0),
        energy=d.get("energy", 0.0),
        gain=tuple((str(k), v) for k, v in (d.get("gain") or {}).items()),
        cost=tuple((str(k), v) for k, v in (d.get("cost") or {}).items()),
        summon=tuple([d["summon"]] if isinstance(d.get("summon"), str) else d.get("summon", ())),
    )


def _action(name: str, d: dict, skill_id: int | None) -> ActionSpec:
    fu = d.get("followup")
    return ActionSpec(
        name=name, hits=[_hitspec(h) for h in d.get("hits", [])],
        lock=float(d.get("lock", DEFAULT_LOCKS.get(name, 0.0))), duration=float(d.get("duration", 0.0)),
        skill_id=d.get("skill_id", skill_id),
        followup=Followup(fu.get("after", ""), fu.get("every", 1), fu.get("event", ""), float(fu.get("delay", 0.0)), bool(fu.get("autos", False)),
                          float(fu["dodge_cancel"]["at"]) if fu.get("dodge_cancel") else None,
                          float(fu["dodge_cancel"]["duration"]) if fu.get("dodge_cancel") else 0.0) if fu else None,
        starts_cd=str(d.get("starts_cd", "")), cd_start=float(d.get("cd_start", 0.0)),
        charges=int(d.get("charges", 0)),
        use_interval=float(d["use_interval"]) if "use_interval" in d else None,
        dodge_at=float(d["dodge_cancel"]["at"]) if d.get("dodge_cancel") else None,
        dodge_duration=float(d["dodge_cancel"]["duration"]) if d.get("dodge_cancel") else 0.0,
    )


def _potential(d: dict) -> PotentialSpec:
    d = d or {}
    return PotentialSpec(
        add_hits={a: [_hitspec(h) for h in hs] for a, hs in (d.get("add_hits") or {}).items()},
        replace_hits={a: [_hitspec(h) for h in hs] for a, hs in (d.get("replace_hits") or {}).items()},
        add_actions={n: _action(n, a, None) for n, a in (d.get("add_actions") or {}).items()},
        overrides=[ModifierOverride(index=o.get("index"), stat=o.get("stat"),
                                    set={k: v for k, v in o.items() if k not in ("index", "stat")})
                   for o in d.get("overrides", [])],
        mark_tags=tuple(d.get("mark_tags", ())),
        extra_casts=dict(d.get("extra_casts", {})),
        reset_cd=dict(d.get("reset_cd", {})),
        cd_reduce=d.get("cd_reduce"),
        procs=[_hitspec(p) for p in d.get("procs", [])],
        add_charges={k: int(v) for k, v in (d.get("add_charges") or {}).items()},
        cd_scale={k: float(v) for k, v in (d.get("cd_scale") or {}).items()},
        cd_when=[dict(c) for c in d.get("cd_when", [])],
        minion_rules={k: dict(v) for k, v in (d.get("minion_rules") or {}).items()},
        ult_cost_scale=float(d.get("ult_cost_scale", 1.0)),
        note=d.get("note", ""),
    )


def _minion(name: str, d: dict) -> MinionSpec:
    s = d.get("summon") or {}
    dur = d.get("duration", "inf")
    return MinionSpec(
        name=name, summon=str(s.get("event", "")), offset=float(s.get("offset", 0.0)),
        every=float(s.get("every", 3.0)), count=int(s.get("count", 1)), restart=bool(s.get("restart", True)),
        max=int(d.get("max", 1)), duration=math.inf if dur in ("inf", None) else float(dur),
        at_max=str(d.get("at_max", "replace")), windup=float(d.get("windup", 0.0)),
        interval=float(d.get("interval", 1.0)), attacks=[_hitspec(h) for h in d.get("attacks", [])],
        sacrifice_on=str(d.get("sacrifice_on", "")), resummon_on=str(d.get("resummon_on", "")),
        speed=float(d.get("speed", 0.0)), reactions=[_hitspec(h) for h in d.get("reactions", [])],
    )


def _buff(b: dict) -> BuffSpec:
    return BuffSpec(effect=int(b["effect"]) if "effect" in b else None, level=b.get("level", "skill"), event=b["event"],
                    duration=b.get("duration", "inf"), target=b.get("target", "self"),
                    max_stacks=b.get("max_stacks", 1), attribute=b.get("attribute"), as_stat=b.get("as_stat"),
                    hit_tags=tuple(b.get("hit_tags", ())), per_stack=bool(b.get("per_stack", False)),
                    name=b.get("name", ""), add=b.get("add", 1),
                    requires=tuple(int(x) for x in b.get("requires", ())),
                    excludes=tuple(int(x) for x in b.get("excludes", ())),
                    requires_all=tuple(int(x) for x in b.get("requires_all", ())),
                    minions=bool(b.get("minions", False)), every=b.get("every", 1), icd=b.get("icd", 0.0),
                    reset_on=tuple(b.get("reset_on", ())))


def role_status(path: Path, role: str) -> str:
    """How far a spec's role kit goes: "ok", "untimed" (`untimed: true`, authored but on guessed timings),
    "stub" (`stub: true`, placeholder hits only) or "missing" (no section)."""
    with open(path, encoding="utf-8") as f:
        sec = yaml.safe_load(f).get(role)
    if sec is None:
        return "missing"
    if sec.get("stub"):
        return "stub"
    return "untimed" if sec.get("untimed") else "ok"


def load_kit(gd: GameData, path: Path, role: str) -> Kit:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    char_id = int(doc["char_id"])
    if role not in doc:
        raise ValueError(f"no {role} kit in the spec (can't be simulated as {role})")
    sec = doc[role]
    ids = skill_ids(gd, char_id, role)
    actions = {}
    for name, a in sec["actions"].items():
        if role == "support" and name == "auto":
            continue
        actions[name] = _action(name, a, ids.get(name))
    buffs = [_buff(b) for b in sec.get("buffs", [])]
    # Talents belong to the Trekker, not the role: top-level entries apply to both, a section's entry wins over them.
    talents = {int(k): TalentSpec(buffs=[_buff(b) for b in (v or {}).get("buffs", [])],
                                  buff_events=dict((v or {}).get("buff_events") or {}), note=(v or {}).get("note", ""))
               for k, v in {**(doc.get("talents") or {}), **(sec.get("talents") or {})}.items()}
    mark = sec.get("mark")
    return Kit(
        char_id=char_id, role=role, actions=actions,
        mark_hit=int(mark["hit"]) if mark else None,
        mark_hit_tags=tuple(mark.get("tags", ())) if mark else (),
        energy_per_second=float(sec.get("energy_per_second", 0.0)),
        energy_conv=gd.table("Character")[str(char_id)].get("EnergyConvRatio", 10000) / 10000,
        potentials={int(k): _potential(v) for k, v in (sec.get("potentials") or {}).items()},
        buffs=buffs,
        reset_cd=dict((sec.get("base_rules") or {}).get("reset_cd", {})),
        on_field={k: float(v) for k, v in (sec.get("on_field") or DEFAULT_ON_FIELD).items()} if role == "support" else {},
        talents=talents,
        minions={k: _minion(k, v) for k, v in (sec.get("minions") or {}).items()},
        procs=[_hitspec(p) for p in sec.get("procs", [])],
        wait_on_field=bool(sec.get("wait_on_field", False)),
        ult_only_with=tuple(int(x) for x in sec.get("ult_only_with", ())),
        resources={k: float((v or {}).get("max", math.inf)) for k, v in (sec.get("resources") or {}).items()},
    )


def pink_ids(gd: GameData, char_id: int, names: list[str], role: str = "main") -> list[int]:
    pinks = potential_pools(gd, char_id, role)["pink"]
    by_name = {gd.item_name(p): p for p in pinks}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise KeyError(f"{gd.char_name(char_id)} {role} pinks not found: {missing}; have {list(by_name)}")
    return [by_name[n] for n in names]


def value(gd: GameData, v, level: int, potential: dict | None = None) -> float:
    """Resolve a YAML value: number, {ref: "..."} or {param: ParamN}, optionally multiplied: {ref:..., times: x}."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        if "ref" in v:
            out = resolve(gd, v["ref"], level).value
        elif "param" in v:
            out = resolve(gd, potential[v["param"]], level).value
        else:
            raise ValueError(f"bad value {v!r}")
        if isinstance(out, list):
            raise ValueError(f"value {v!r} resolved to a list")
        return float(out) * float(v.get("times", 1))
    raise ValueError(f"bad value {v!r}")


def _apply_override(gd, m: Modifier, s: dict, level: int, pot: dict) -> Modifier | None:
    if s.get("drop"):
        return None
    kw = {}
    if "hit_tags" in s:
        kw["hit_tags"] = tuple(s["hit_tags"])
        kw["needs_scope"] = False
    if "target" in s:
        kw["target"] = s["target"]
    if "as_stat" in s:
        kw["stat"] = int(s["as_stat"])
    if "minions" in s:
        kw["minions"] = bool(s["minions"])
    if "pct" in s:   # e.g. an attribute that decodes as flat ATK but the text says "ATK by 39%"
        kw["is_pct"] = bool(s["pct"])
    if "stacks" in s:  # constant stack count folded into the value
        n = (m.trigger.max_stacks if (s["stacks"] == "max" and m.trigger) else value(gd, s["stacks"], level, pot))
        kw["value"] = m.value * n
    if "value" in s:
        kw["value"] = value(gd, s["value"], level, pot)
    trig_keys = {"event", "duration", "max_stacks", "uptime", "icd", "per_stack", "stacks_from", "reset_on", "every"}
    if trig_keys & set(s):
        base = m.trigger or Trigger(event="unknown", duration=math.inf)
        dur = s.get("duration", base.duration)
        tkw = dict(
            event=s.get("event", base.event),
            duration=math.inf if dur in ("inf", None) else value(gd, dur, level, pot),
            max_stacks=int(value(gd, s.get("max_stacks", base.max_stacks), level, pot)),
            uptime=s.get("uptime", base.uptime),
            icd=value(gd, s.get("icd", base.icd), level, pot),
            every=int(value(gd, s.get("every", base.every), level, pot)),
            per_stack=bool(s.get("per_stack", base.per_stack)),
            stacks_from=s.get("stacks_from", base.stacks_from),
            add=base.add,
            reset_on=tuple(s.get("reset_on", base.reset_on)),
        )
        trig = Trigger(**tkw)
        if trig.event == "always":
            trig = None
        kw["trigger"] = trig
        kw["assumed"] = trig is not None and trig.event == "unknown" and trig.uptime is None
    if "stacks" in s and "max_stacks" not in s and kw.get("trigger", m.trigger) is not None:
        t = kw.get("trigger", m.trigger)
        kw["trigger"] = replace(t, max_stacks=1)
    return m.with_(**kw)


def resolve_potential(gd: GameData, kit: Kit, potential_id: int, level: int) -> ResolvedPotential:
    mods, notes = potential_modifiers(gd, potential_id, level)
    spec = kit.potentials.get(potential_id, PotentialSpec())
    pot = gd.table("Potential")[str(potential_id)]
    out: list[Modifier] = []
    from .effects import with_minion_scope
    mods = with_minion_scope(mods, gd.text(f"Potential.{potential_id}.2") or "")
    for i, m in enumerate(mods):
        cur = [m]
        for o in spec.overrides:
            if (o.index is not None and o.index == i) or (o.index is None and o.stat == m.stat):
                base = {k: v for k, v in o.set.items() if k != "copies"}
                sets = [{**base, **c} for c in o.set["copies"]] if "copies" in o.set else [base]
                cur = [x for x in (_apply_override(gd, c, st, level, pot) for c in cur for st in sets) if x is not None]
        out += cur
    cd_reduce = None
    if spec.cd_reduce:
        cd_reduce = {"action": spec.cd_reduce.get("action", "skill"),
                     "seconds": value(gd, spec.cd_reduce["seconds"], level, pot),
                     "times": value(gd, spec.cd_reduce.get("times", 1), level, pot)}
    procs = [HitSpec(**{**p.__dict__, "icd": value(gd, p.icd, level, pot),
                        "resilience": value(gd, p.resilience, level, pot),
                        "energy": value(gd, p.energy, level, pot),
                        "gain": tuple((r, value(gd, v, level, pot)) for r, v in p.gain),
                        "cost": tuple((r, value(gd, v, level, pot)) for r, v in p.cost),
                        "every": max(1, int(round(value(gd, p.every, level, pot))))}) for p in spec.procs]
    add_actions = {n: replace(a, followup=replace(a.followup, every=max(1, int(round(value(gd, a.followup.every, level, pot))))))
                   if a.followup else a for n, a in spec.add_actions.items()}
    def rule(k, v):
        if k == "reactions":
            return [replace(h, icd=value(gd, h.icd, level, pot)) for h in (_hitspec(x) for x in v)]
        return value(gd, v, level, pot) if isinstance(v, dict) else v
    minion_rules = {pool: {k: rule(k, v) for k, v in r.items()} for pool, r in spec.minion_rules.items()}
    if spec.note:
        notes = notes + [spec.note]
    return ResolvedPotential(
        potential_id=potential_id, level=level, modifiers=out, notes=notes,
        add_hits=spec.add_hits, replace_hits=spec.replace_hits, add_actions=add_actions,
        mark_tags=spec.mark_tags, extra_casts=spec.extra_casts, reset_cd=spec.reset_cd,
        cd_reduce=cd_reduce, procs=procs, add_charges=spec.add_charges, cd_scale=spec.cd_scale,
        minion_rules=minion_rules, cd_when=spec.cd_when, ult_cost_scale=spec.ult_cost_scale,
    )


def kit_buffs(kit: Kit, talent_ids: list[int]) -> list[BuffSpec]:
    """The kit's base buffs plus what the unlocked key talents add or change."""
    buffs = list(kit.buffs)
    for tid in talent_ids:
        ts = kit.talents.get(tid)
        if ts is None:
            continue
        buffs = [replace(b, event=f"{b.event}|{ts.buff_events[b.name]}") if b.name in ts.buff_events else b
                 for b in buffs]
        buffs += ts.buffs
    return buffs


def resolve_buffs(gd: GameData, kit: Kit, skill_levels: dict[str, int], owned: set | None = None,
                  buffs: list[BuffSpec] | None = None) -> list[Modifier]:
    """Modifiers granted by base skills (e.g. Noya's Starender, Glimmer), leveled by skill level."""
    from .effects import _oaa_row_modifiers
    out = []
    owned = owned or set()
    for b in (kit.buffs if buffs is None else buffs):
        if ((b.requires and not any(r in owned for r in b.requires)) or any(e in owned for e in b.excludes)
                or not all(r in owned for r in b.requires_all)):
            continue
        lv = skill_levels.get(b.level, 10)
        dur = math.inf if b.duration == "inf" else value(gd, b.duration, lv)
        trig = None if b.event == "always" else Trigger(
            event=b.event, duration=dur, max_stacks=int(value(gd, b.max_stacks, lv)), per_stack=b.per_stack,
            add=int(value(gd, b.add, lv)), every=int(value(gd, b.every, lv)), icd=value(gd, b.icd, lv),
            reset_on=b.reset_on)
        src = f"{gd.char_name(kit.char_id)} {b.level} {'status ' + b.name if b.name else 'buff'} ({b.effect or b.attribute})"
        def row(table: str, base: int) -> dict:
            # A row at the id itself is single-level (e.g. a talent's). id + level*10 could be an unrelated row.
            return gd.table(table).get(str(base)) or level_row(gd, table, base, lv)
        if b.attribute is not None:
            mods = _oaa_row_modifiers(row("OnceAdditionalAttributeValue", b.attribute), src)
        elif b.effect is None:   # pure status (e.g. a minion count): no stat, only stacks
            mods = [Modifier(stat=0, value=0.0, source=src)]
        else:
            notes: list[str] = []
            vrow = row("EffectValue", b.effect)
            mods = _interpret(gd, gd.table("Effect").get(str(b.effect)), vrow, src, notes, trig, None)
        for m in mods:
            kw = dict(trigger=trig, assumed=False, needs_scope=False, name=b.name,
                      target=b.target if m.target != "enemy" or b.target == "enemy" else "enemy")
            if b.as_stat is not None:
                kw["stat"] = int(b.as_stat)
            if b.hit_tags:
                kw["hit_tags"] = b.hit_tags
            kw["minions"] = b.minions
            out.append(m.with_(**kw))
    return out
