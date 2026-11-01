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
    # procs only
    event: str = ""
    icd: float = 0.0


@dataclass
class Followup:
    after: str
    every: int


@dataclass
class ActionSpec:
    name: str
    hits: list[HitSpec]
    lock: float = 0.0
    duration: float = 0.0
    skill_id: int | None = None
    followup: Followup | None = None


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


@dataclass
class Kit:
    char_id: int
    role: str
    actions: dict[str, ActionSpec]
    mark_hit: int | None = None
    energy_per_second: float = 0.0
    energy_conv: float = 1.0
    potentials: dict[int, PotentialSpec] = field(default_factory=dict)
    buffs: list[BuffSpec] = field(default_factory=list)
    reset_cd: dict[str, str] = field(default_factory=dict)
    on_field: dict[str, float] = field(default_factory=dict)   # support: seconds on the battlefield per cast


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


def _hitspec(d: dict) -> HitSpec:
    return HitSpec(
        hit_id=int(d["hit"]), count=int(d.get("count", 1)), offset=float(d.get("offset", 0.0)),
        interval=float(d.get("interval", 0.1)), tags=tuple(d.get("tags", ())),
        triggers_mark=bool(d.get("triggers_mark", False)), applies_mark=bool(d.get("applies_mark", False)),
        requires=tuple(int(x) for x in d.get("requires", ())), excludes=tuple(int(x) for x in d.get("excludes", ())),
        event=str(d.get("event", "")), icd=d.get("icd", 0.0),
    )


def _action(name: str, d: dict, skill_id: int | None) -> ActionSpec:
    fu = d.get("followup")
    return ActionSpec(
        name=name, hits=[_hitspec(h) for h in d.get("hits", [])],
        lock=float(d.get("lock", DEFAULT_LOCKS.get(name, 0.0))), duration=float(d.get("duration", 0.0)),
        skill_id=d.get("skill_id", skill_id),
        followup=Followup(fu["after"], int(fu["every"])) if fu else None,
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
        note=d.get("note", ""),
    )


def load_kit(gd: GameData, path: Path, role: str) -> Kit:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    char_id = int(doc["char_id"])
    sec = doc[role]
    ids = skill_ids(gd, char_id, role)
    actions = {}
    for name, a in sec["actions"].items():
        if role == "support" and name == "auto":
            continue
        actions[name] = _action(name, a, ids.get(name))
    buffs = [BuffSpec(effect=int(b["effect"]) if "effect" in b else None, level=b["level"], event=b["event"],
                      duration=b.get("duration", "inf"), target=b.get("target", "self"),
                      max_stacks=b.get("max_stacks", 1), attribute=b.get("attribute"), as_stat=b.get("as_stat"),
                      hit_tags=tuple(b.get("hit_tags", ())), per_stack=bool(b.get("per_stack", False)),
                      name=b.get("name", ""))
             for b in sec.get("buffs", [])]
    mark = sec.get("mark")
    return Kit(
        char_id=char_id, role=role, actions=actions,
        mark_hit=int(mark["hit"]) if mark else None,
        energy_per_second=float(sec.get("energy_per_second", 0.0)),
        energy_conv=gd.table("Character")[str(char_id)].get("EnergyConvRatio", 10000) / 10000,
        potentials={int(k): _potential(v) for k, v in (sec.get("potentials") or {}).items()},
        buffs=buffs,
        reset_cd=dict((sec.get("base_rules") or {}).get("reset_cd", {})),
        on_field={k: float(v) for k, v in (sec.get("on_field") or DEFAULT_ON_FIELD).items()} if role == "support" else {},
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
    if "stacks" in s:  # constant stack count folded into the value
        n = (m.trigger.max_stacks if (s["stacks"] == "max" and m.trigger) else value(gd, s["stacks"], level, pot))
        kw["value"] = m.value * n
    if "value" in s:
        kw["value"] = value(gd, s["value"], level, pot)
    trig_keys = {"event", "duration", "max_stacks", "uptime", "icd", "per_stack", "stacks_from"}
    if trig_keys & set(s):
        base = m.trigger or Trigger(event="unknown", duration=math.inf)
        dur = s.get("duration", base.duration)
        tkw = dict(
            event=s.get("event", base.event),
            duration=math.inf if dur in ("inf", None) else value(gd, dur, level, pot),
            max_stacks=int(s.get("max_stacks", base.max_stacks)),
            uptime=s.get("uptime", base.uptime),
            icd=float(s.get("icd", base.icd)),
            every=base.every,
            per_stack=bool(s.get("per_stack", base.per_stack)),
            stacks_from=s.get("stacks_from", base.stacks_from),
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
    for i, m in enumerate(mods):
        for o in spec.overrides:
            if (o.index is not None and o.index == i) or (o.index is None and o.stat == m.stat):
                m = _apply_override(gd, m, o.set, level, pot)
                if m is None:
                    break
        if m is not None:
            out.append(m)
    cd_reduce = None
    if spec.cd_reduce:
        cd_reduce = {"action": spec.cd_reduce.get("action", "skill"),
                     "seconds": value(gd, spec.cd_reduce["seconds"], level, pot),
                     "times": value(gd, spec.cd_reduce.get("times", 1), level, pot)}
    procs = [HitSpec(**{**p.__dict__, "icd": value(gd, p.icd, level, pot)}) for p in spec.procs]
    if spec.note:
        notes = notes + [spec.note]
    return ResolvedPotential(
        potential_id=potential_id, level=level, modifiers=out, notes=notes,
        add_hits=spec.add_hits, replace_hits=spec.replace_hits, add_actions=spec.add_actions,
        mark_tags=spec.mark_tags, extra_casts=spec.extra_casts, reset_cd=spec.reset_cd,
        cd_reduce=cd_reduce, procs=procs,
    )


def resolve_buffs(gd: GameData, kit: Kit, skill_levels: dict[str, int]) -> list[Modifier]:
    """Modifiers granted by base skills (e.g. Noya's Starender, Glimmer), leveled by skill level."""
    from .effects import _oaa_row_modifiers
    out = []
    for b in kit.buffs:
        lv = skill_levels.get(b.level, 10)
        dur = math.inf if b.duration == "inf" else value(gd, b.duration, lv)
        trig = Trigger(event=b.event, duration=dur, max_stacks=int(value(gd, b.max_stacks, lv)), per_stack=b.per_stack)
        src = f"{gd.char_name(kit.char_id)} {b.level} {'status ' + b.name if b.name else 'buff'} ({b.effect or b.attribute})"
        if b.attribute is not None:
            mods = _oaa_row_modifiers(level_row(gd, "OnceAdditionalAttributeValue", b.attribute, lv), src)
        else:
            notes: list[str] = []
            vrow = level_row(gd, "EffectValue", b.effect, lv)
            mods = _interpret(gd, gd.table("Effect").get(str(b.effect)), vrow, src, notes, trig, None)
        for m in mods:
            kw = dict(trigger=trig, assumed=False, needs_scope=False, name=b.name,
                      target=b.target if m.target != "enemy" or b.target == "enemy" else "enemy")
            if b.as_stat is not None:
                kw["stat"] = int(b.as_stat)
            if b.hit_tags:
                kw["hit_tags"] = b.hit_tags
            out.append(m.with_(**kw))
    return out
