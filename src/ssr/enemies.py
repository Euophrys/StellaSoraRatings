"""Enemies: values from game data (resilience, DEF, RES per element) and the presets in specs/enemies."""
from __future__ import annotations

from functools import lru_cache

import yaml

from .data import GameData, REPO_ROOT
from .effects import _spec_modifiers
from .formula import Enemy
from .kit import value

# MonsterValueTempleteAdjust RES fields by element (EET): Aqua, Ignis, Terra, Ventus, Lux, Umbra
RES_FIELDS = {1: "WERFix", 2: "FERFix", 3: "SERFix", 4: "AERFix", 5: "LERFix", 6: "DERFix"}


def monster_values(gd: GameData, monster_id: int) -> dict:
    """Resilience, break time, refill, DEF, raw RES per element, weak elements and element of a monster.
    Chain: Monster.Templete -> MonsterValueTempleteAdjust -> MonsterValueTemplete (same TemplateId)."""
    m = gd.table("Monster")[str(monster_id)]
    adj = gd.table("MonsterValueTempleteAdjust")[str(m["Templete"])]
    rows = [r for r in gd.table("MonsterValueTemplete").values()
            if r.get("TemplateId") == adj["TemplateId"] and r.get("Toughness")]
    if not rows:
        raise KeyError(f"monster {monster_id}: no MonsterValueTemplete row with Toughness")
    v = rows[0]
    return dict(
        resilience=v["Toughness"] * (1 + adj.get("ToughnessRatio", 0) / 10000),
        break_time=m.get("ToughnessBrokenTime", 0) / 10000,
        refill=bool(m.get("IsToughnessRecorver", False)),
        defense=float(v.get("Def", 0)),
        res={el: adj.get(f, 0) for el, f in RES_FIELDS.items()},
        weak=list(adj.get("WeakEET") or []),
        element=adj.get("EET"),
    )


ENEMY_SPECS = REPO_ROOT / "specs" / "enemies"
_ELEMENT_IDS = {"aqua": 1, "ignis": 2, "terra": 3, "ventus": 4, "lux": 5, "umbra": 6}
PRESET_DEFAULTS = dict(break_ratio=1.5, lock_delay=1.3, lock_time=4.7, baseline_pen=105)
_FLOAT_KEYS = ("resilience", "break_time", "break_ratio", "lock_delay", "lock_time")


def _res_by_element(e: dict) -> dict[int, float]:
    """`weak: [Umbra]` + `res_neutral: 645`: the weak elements keep `res`, every other element gets `res_neutral`.
    Without `weak`, every element uses `res`."""
    weak = e.get("weak")
    if not weak:
        return {}
    ids = {w if isinstance(w, int) else _ELEMENT_IDS[str(w).lower()] for w in weak}
    neutral = float(e.get("res_neutral", 645))
    return {el: neutral for el in range(1, 7) if el not in ids}


def preset_names() -> list[str]:
    names = sorted(p.stem for p in ENEMY_SPECS.glob("*.yaml"))
    return ["generic"] + [n for n in names if n != "generic"]


@lru_cache(maxsize=None)
def _preset_doc(name: str) -> dict:
    p = ENEMY_SPECS / f"{name}.yaml"
    if name not in preset_names():   # only listed presets: no paths, no typos
        raise KeyError(f"unknown enemy preset {name!r}; have {preset_names()}")
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_refs(gd: GameData, entry: dict) -> dict:
    return {k: (value(gd, v, 1) if isinstance(v, dict) and "ref" in v else v) for k, v in entry.items()}


def _preset(gd: GameData, name: str) -> dict:
    """The preset's values: defaults, then monster data, then the preset file's own keys."""
    doc = _preset_doc(name)
    out = dict(PRESET_DEFAULTS, res=145.0, defense=500.0, resilience=0.0, break_time=10.0,
               res_by_element={}, fight_length=None)
    pen = float(doc.get("baseline_pen", out["baseline_pen"]))
    if "monster" in doc:
        mv = monster_values(gd, int(doc["monster"]))
        by_el = {el: float(raw) - pen for el, raw in mv["res"].items()}
        out.update(res=min(by_el.values()), defense=mv["defense"], resilience=mv["resilience"],
                   break_time=mv["break_time"], res_by_element=by_el)
    for k in ("res", "defense", "fight_length", *_FLOAT_KEYS):
        if doc.get(k) is not None:
            out[k] = float(doc[k])
    label = doc.get("label", name)
    out["label"] = label
    out["ability"] = tuple(_spec_modifiers([_resolve_refs(gd, e) for e in doc.get("ability") or []], {},
                                           f"{label} ability"))
    return out


def enemy_from_doc(gd: GameData, e: dict | None) -> Enemy:
    """A team file's `enemy:` block: `preset` (default generic), then any of res, defense, broken, weak/res_neutral,
    resilience, break_time, break_ratio, lock_delay, lock_time override the preset."""
    e = e or {}
    name = str(e.get("preset", "generic"))
    p = _preset(gd, name)
    by_el = dict(p["res_by_element"])
    res = p["res"]
    if "res" in e:
        new = float(e["res"])
        # a RES override moves the preset's weak elements (those at the preset's `res`) with it
        by_el = {el: (new if v == res else v) for el, v in by_el.items()}
        res = new
    if e.get("weak"):
        by_el = _res_by_element(e)
    kw = {k: float(e[k]) if k in e else p[k] for k in _FLOAT_KEYS}
    return Enemy(res=res, defense=float(e.get("defense", p["defense"])), broken=float(e.get("broken", 1.0)),
                 res_by_element=by_el, name=name, ability=p["ability"], fight_length=p["fight_length"], **kw)


def preset_label(name: str) -> str:
    try:
        return str(_preset_doc(name).get("label", name))
    except KeyError:
        return name


def enemy_summary(enemy: Enemy, breaks: int | None = None) -> str:
    """One line for reports: preset, RES/DEF and the bar."""
    s = f"{preset_label(enemy.name)}, RES {enemy.res:g}, DEF {enemy.defense:g}"
    if enemy.resilience > 0:
        s += f", resilience {enemy.resilience / 1e6:g}M, break x{enemy.break_ratio:g} for {enemy.break_time:g} s"
        if breaks is not None:
            s += f", {breaks} breaks in the baseline"
    else:
        s += ", no resilience bar"
    return s


def preset_catalog(gd: GameData) -> list[dict]:
    """The presets for the web page's enemy dropdown."""
    out = []
    for n in preset_names():
        p = _preset(gd, n)
        out.append(dict(id=n, label=p["label"], fight_length=p["fight_length"], res=p["res"],
                        defense=p["defense"], resilience=p["resilience"]))
    return out
