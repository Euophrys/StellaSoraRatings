"""Frame data read from the game's own asset bundles (no decryption: they're plain Unity bundles).

Per character, the `char_<id>01_combos` bundle has one ComboClip per animation (each auto strike, skill, ult, dodge),
with its length, play speed, combo window and a timed event list. Hit events carry a `HitDamage` id; bullet and
area events point at prefabs in `char_<id>01_weapons`, which carry their own hit ids, delays, intervals, speeds and
lifetimes. Type-0 events are calls into the game's (encrypted) Lua: only their name and time are known.

    python -m ssr.frames extract [<char id> ...]   # read bundles -> data_src/frames/<id>.json (all if none given)
    python -m ssr.inspect frames <char>             # print it

Needs UnityPy (`pip install UnityPy`) and the installed game, only to extract. `SSR_GAME_DIR` overrides the
default Steam path. Times are seconds at 1x speed: `at` = normalized time x clip length / play speed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from .data import REPO_ROOT

GAME_DIR = Path(os.environ.get("SSR_GAME_DIR", "~/.local/share/Steam/steamapps/common/Stella Sora")).expanduser()
BUNDLE_DIRS = [GAME_DIR / "Persistent_Store" / "AssetBundles",               # patched copies win
               GAME_DIR / "StellaSora_Data" / "StreamingAssets" / "InstallResource"]
CACHE = REPO_ROOT / "data_src" / "frames"

EVENT_TYPES = {0: "script", 1: "hit", 2: "bullet", 3: "buff", 5: "area", 8: "type8", 10: "type10", 20: "card",
               9: "audio", 90: "fx", -90: "fx"}
SKIP_TYPES = {9, 90, -90, 20}     # audio, visual effects, fate cards
COMBO_SKILL_TYPES = {1: "auto", 2: "dodge", 3: "skill", 4: "sprint", 5: "ult"}


def _fx(v):
    """Fixed-point Q32.32 values ({_serializedValue: n}) -> float."""
    if isinstance(v, dict) and "_serializedValue" in v:
        return v["_serializedValue"] / 2 ** 32
    return v


def _r(x, n=3):
    return round(x, n) if isinstance(x, float) else x


def _bundles(cid: int) -> list[Path]:
    seen: dict[str, Path] = {}
    pat = re.compile(rf"char_{cid}01_(combos|weapons)\w*\.unity3d$")
    for d in BUNDLE_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if pat.match(p.name) and p.name not in seen:
                seen[p.name] = p
    return list(seen.values())


class _Index:
    """Every object of the loaded bundles, keyed by (CAB name, path id), so cross-bundle PPtrs resolve."""

    def __init__(self, env):
        self.objs = {}
        self.files = {}
        for bundle in env.files.values():
            for name, sf in getattr(bundle, "files", {}).items():
                if not hasattr(sf, "objects"):
                    continue
                self.files[name.lower()] = sf
                for pid, o in sf.objects.items():
                    self.objs[(name.lower(), pid)] = o
        self._tt = {}

    def cab(self, sf):
        for k, v in self.files.items():
            if v is sf:
                return k
        return None

    def resolve(self, cab, ptr):
        """A PPtr ({m_FileID, m_PathID}) seen in file `cab` -> (cab, path id) of its target, or None."""
        if not ptr or not ptr.get("m_PathID"):
            return None
        fid = ptr.get("m_FileID", 0)
        if fid == 0:
            return (cab, ptr["m_PathID"])
        ext = self.files[cab].externals[fid - 1].path
        return (ext.rsplit("/", 1)[-1].lower(), ptr["m_PathID"])

    def tree(self, key):
        if key not in self._tt:
            o = self.objs.get(key)
            self._tt[key] = o.read_typetree() if o is not None else None
        return self._tt[key]

    def script_name(self, cab, mb):
        k = self.resolve(cab, mb.get("m_Script"))
        t = self.tree(k) if k in self.objs else None
        return t.get("m_ClassName") if t else None


def _prefab(ix: _Index, key, seen=None) -> dict | None:
    """A bullet / area prefab (a GameObject and its children) -> what it does."""
    if key is None or key not in ix.objs:
        return None
    seen = seen if seen is not None else set()
    if key in seen:
        return {"ref": ix.tree(key).get("m_Name")}
    seen.add(key)
    cab = key[0]
    go = ix.tree(key)
    out = {"name": go.get("m_Name"), "parts": []}
    stack = [key]
    while stack:
        gk = stack.pop()
        g = ix.tree(gk)
        for comp in g.get("m_Component", []):
            ck = ix.resolve(cab, comp.get("component"))
            if ck not in ix.objs:
                continue
            o = ix.objs[ck]
            if o.type.name == "Transform":
                for ch in ix.tree(ck).get("m_Children", []):
                    tk = ix.resolve(cab, ch)
                    if tk in ix.objs:
                        stack.append(ix.resolve(cab, ix.tree(tk)["m_GameObject"]))
                continue
            if o.type.name != "MonoBehaviour":
                continue
            mb = ix.tree(ck)
            cls = ix.script_name(cab, mb)
            part = _part(ix, cab, cls, mb, seen)
            if part:
                out["parts"].append(part)
    return out


def _part(ix, cab, cls, mb, seen):
    if cls in (None, "AkWeaponHitSwitch") or cls.startswith("Ak"):
        return None
    p = {"class": cls}
    for k in ("hitDamageId", "hitDelay", "hitInterval", "hitImmediately", "triggerStay", "time_TriggerStay",
              "duration", "moveSpeed", "acceleratedVelocity", "borderVelocitySpeed", "lifeTime", "areaTag",
              "damageImmuneDuration", "blockCount", "addBuffIdList", "addInterval", "buffIds", "maxHitCount",
              "hitCount", "count", "interval", "delay", "bulletCount", "speed", "moveInterval",
              "genBegin", "genEnd", "genInterval", "genCount", "lockTarget", "penetrateCount", "canPenetrate"):
        if k in mb:
            v = _fx(mb[k])
            if v not in (0, 0.0, "", [], None):
                p[k] = _r(v)
    for k, v in mb.items():   # every prefab reference: what this part spawns
        if isinstance(v, dict) and "m_PathID" in v and k.lower().endswith("prefab") and k not in (
                "fxPrefab", "hittedPrefab", "hittedEffectPrefab", "finishPrefab", "triggerFx", "fx"):
            sub = _prefab(ix, _go_of(ix, ix.resolve(cab, v)), seen)
            if sub:
                p.setdefault("spawns", []).append({"via": k, **sub})
        elif isinstance(v, list) and v and isinstance(v[0], dict) and "m_PathID" in v[0] and "prefab" in k.lower():
            for it in v:
                sub = _prefab(ix, _go_of(ix, ix.resolve(cab, it)), seen)
                if sub:
                    p.setdefault("spawns", []).append({"via": k, **sub})
    return p if len(p) > 1 else None


def _go_of(ix, key):
    """A PPtr to a prefab may point at its GameObject or one of its components."""
    if key is None or key not in ix.objs:
        return None
    o = ix.objs[key]
    if o.type.name == "GameObject":
        return key
    t = ix.tree(key)
    return ix.resolve(key[0], t.get("m_GameObject"))


def _event(ix, cab, e, real):
    t = e["type"]
    a, b = _fx(e["activeNormalizedTimeRange"]["x"]), _fx(e["activeNormalizedTimeRange"]["y"])
    ev = {"type": EVENT_TYPES.get(t, str(t)), "at": _r(a * real), "norm": _r(a)}
    if b and b != a:
        ev["until"] = _r(b * real)
    for k in ("tag", "name"):
        if e.get(k):
            ev[k] = e[k]
    if e.get("hitDamageId"):
        ev["hit"] = e["hitDamageId"]
    if _fx(e.get("damageDetectInterval")):
        ev["detect_interval"] = _r(_fx(e["damageDetectInterval"]))
    if (_fx(e.get("damageImmuneDuration")) or 0) > 0:
        ev["immune"] = _r(_fx(e["damageImmuneDuration"]))
    if e.get("buffIds"):
        ev["buffs"] = e["buffIds"]
    if t == 2:
        ev["count"] = e.get("bulletCount", 1)
        ev["prefab"] = _prefab(ix, _go_of(ix, ix.resolve(cab, e.get("bulletPrefab"))))
    if t == 5:
        ev["prefab"] = _prefab(ix, _go_of(ix, ix.resolve(cab, e.get("AreaEffectPrefab"))))
    return ev


def extract(cid: int) -> dict:
    import UnityPy   # optional: only needed to read the bundles

    paths = _bundles(cid)
    if not any("_combos" in p.name for p in paths):
        raise FileNotFoundError(f"no combos bundle for char {cid} under {GAME_DIR}")
    env = UnityPy.load(*map(str, paths))
    ix = _Index(env)
    skin = cid * 100 + 1
    clips, groups, refs = {}, [], {}
    for (cab, pid), o in ix.objs.items():
        if o.type.name != "MonoBehaviour":
            continue
        mb = ix.tree((cab, pid))
        if "comboEventSkins" in mb:
            L, sp = _fx(mb["animationLength"]), _fx(mb["playSpeed"]) or 1.0
            real = L / sp
            skins = mb["comboEventSkins"]
            evs = next((s["comboEvents"] for s in skins if s["skinId"] == skin), skins[0]["comboEvents"] if skins else [])
            c = {"length": _r(L), "speed": _r(sp), "duration": _r(real),
                 "combo": [_r(_fx(mb["comboPhaseRange"]["x"]) * real), _r(_fx(mb["comboPhaseRange"]["y"]) * real)],
                 "skill_cancel": _r(_fx(mb["skillAllowOtherSkillExecuteNormalizedTime"]) * real)}
            if mb.get("useExitTime"):
                c["exit"] = _r(_fx(mb["canExitNormalizedTime"]) * real)
            c["events"] = sorted((_event(ix, cab, e, real) for e in evs if e["type"] not in SKIP_TYPES),
                                 key=lambda e: e["at"])
            if mb.get("enableExtraEventGroup"):   # alternative event lists a combo row picks by eventGroupTag
                for grp in mb.get("EventGroups") or []:
                    gs = grp["ComboEventSkins"]
                    gev = next((s["comboEvents"] for s in gs if s["skinId"] == skin), gs[0]["comboEvents"] if gs else [])
                    c.setdefault("event_groups", {})[str(grp["index"])] = {
                        "tag": grp.get("tag", ""),
                        "events": sorted((_event(ix, cab, e, real) for e in gev if e["type"] not in SKIP_TYPES),
                                         key=lambda e: e["at"])}
            name = mb["m_Name"]
            clips[name] = c
            refs[(cab, pid)] = name
        elif "combos" in mb and "comboMode" in mb:
            groups.append((cab, mb))
    out_groups = []
    for cab, g in groups:
        rows = []
        for c in g["combos"]:
            rows.append({"kind": COMBO_SKILL_TYPES.get(c["comboSkillType"], str(c["comboSkillType"])),
                         "tag": c["actionTag"], "keys": c["requestKeys"], "mode": c["comboClipMode"],
                         "clips": [refs.get(ix.resolve(cab, cc["comboClip"]), "?") for cc in c["compositeComboClips"]],
                         "event_groups": [int(cc.get("eventGroupTag", "0").split(":")[0] or 0)
                                          for cc in c["compositeComboClips"]]})
        extra = {}
        for k in ("reloadAnimClip", "aimStartAnimClip", "aimAnimClip"):   # ranged Trekkers: reload and raising the gun
            n = refs.get(ix.resolve(cab, g.get(k)))
            if n:
                extra[k.replace("AnimClip", "")] = n
        for k in ("reloadAnimClip_Other",):
            ns = [refs.get(ix.resolve(cab, x)) for x in g.get(k) or []]
            if any(ns):
                extra["reload_other"] = [n for n in ns if n]
        out_groups.append({"name": g["m_Name"], "combos": rows, **extra})
    # weapons no clip points at: spawned by the (encrypted) Lua scripts, keyed by their name
    used = json.dumps(clips)
    loose = {}
    for (cab, pid), o in ix.objs.items():
        if o.type.name != "GameObject":
            continue
        n = ix.tree((cab, pid)).get("m_Name", "")
        if re.match(r"(Bullet|AreaEffect|Area|Laser|Trap|Summon)", n) and f'"{n}"' not in used:
            p = _prefab(ix, (cab, pid))
            if p and p["parts"]:
                loose[n] = p
    return {"char": cid, "bundles": [p.name for p in paths], "groups": out_groups, "clips": clips,
            "script_weapons": dict(sorted(loose.items()))}


def load(cid: int) -> dict | None:
    p = CACHE / f"{cid}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---- timing rules (calibrated against the user's frame timings, docs/assumptions.md "Frame data") ----
#
# * The next auto strike, and the main's next action after a skill or ult, starts at the end of the clip's combo
#   window (`combo[1]`). FL Noya, Gerie, Chitose, Mistique, Leafia and Noya's timed strings and locks agree within
#   ~0.1 s.
# * A hit event lands at its time; with an active range and a detect interval, every interval across the range
#   (FL Noya's skill and ult windows give the text's x5 and x7), or every immunity window if that's longer.
# * An area's attack lands `hitDelay` after it spawns, then every `hitInterval` while the area lasts. A target
#   can't be hit again within `damageImmuneDuration` (Teresa's spin kick: every 0.05 s, immune 3 s: one hit).
# * A bullet lands after flying BULLET_DISTANCE (GUESS: the boss ~3 units away; Ann's ult measured +0.97 for a
#   0.75 s shot, a 25 u/s bullet and a 0.1 s delay), capped by its lifetime; what it spawns on finishing starts then.

BULLET_DISTANCE = 3.0


def _travel(part):
    v, a = part.get("moveSpeed") or 0.0, part.get("acceleratedVelocity") or 0.0
    life = part.get("lifeTime") or 1.0
    if v <= 0:
        return 0.0
    if a:   # constant acceleration, floored at borderVelocitySpeed
        t, x, dt, floor = 0.0, 0.0, 0.005, part.get("borderVelocitySpeed") or 0.0
        while x < BULLET_DISTANCE and t < life:
            x += max(v + a * t, floor) * dt
            t += dt
        return round(min(t, life), 3)
    return round(min(BULLET_DISTANCE / v, life), 3)


def prefab_hits(p: dict | None, t0: float, src: str = "") -> list[tuple[float, int, str]]:
    """(time, HitDamage id, what) for every hit a bullet / area prefab lands, spawning at t0."""
    out = []
    if not p:
        return out
    parts = p.get("parts", [])
    bullet = next((x for x in parts if x["class"] == "AdventureBullet"), None)
    area = next((x for x in parts if x["class"] == "AreaEffectEntity"), None)
    end = t0
    if bullet:
        end = t0 + _travel(bullet)
        if bullet.get("hitDamageId") and bullet["hitDamageId"] != 1000001:
            out.append((round(end, 3), bullet["hitDamageId"], f"{src}{p['name']}"))
    for x in parts:
        if x["class"] == "AdventureBullet" or "hitDamageId" not in x:
            continue
        dur = (area or {}).get("duration", 1.0)
        t, iv = x.get("hitDelay", 0.0), x.get("hitInterval") or 0.0
        if iv and (x.get("damageImmuneDuration") or 0) > iv:   # a target can't be hit again while immune
            iv = x["damageImmuneDuration"]
        while True:
            out.append((round(t0 + t, 3), x["hitDamageId"], f"{src}{p['name']}"))
            if not iv or iv >= 90 or t + iv > dur + 1e-6:
                break
            t += iv
    for x in parts:
        for s in x.get("spawns", []):
            start = end if (bullet and x["class"].startswith("WeaponFeatureFinish")) else t0
            out += prefab_hits(s, start, f"{src}{p['name']} > ")
    return out


def clip_hits(c: dict, t0: float = 0.0, speed: float = 1.0) -> list[tuple[float, int | str, str]]:
    """Every hit of a clip at `speed` (ATK SPD), from t0, sorted. Script events come as (time, 'script', name)."""
    out = []
    for e in c["events"]:
        at = t0 + e["at"] / speed
        if e["type"] == "hit" and e.get("hit"):
            if "until" in e and e.get("detect_interval"):
                t, iv = e["at"], max(e["detect_interval"], e.get("immune", 0))
                while t <= e["until"] + 1e-6:
                    out.append((round(t0 + t / speed, 3), e["hit"], "hit"))
                    t += iv
            else:
                out.append((round(at, 3), e["hit"], "hit"))
        elif e["type"] in ("bullet", "area"):
            for _ in range(max(1, e.get("count", 1)) if e["type"] == "bullet" else 1):
                out += prefab_hits(e.get("prefab"), at)
        elif e["type"] == "script":
            out.append((round(at, 3), "script", e.get("name") or e.get("tag") or ""))
    return sorted(out, key=lambda x: x[0])


def auto_chain(d: dict, tags: list[str] | None = None) -> dict:
    """The auto string: strikes chained at each clip's combo-window end. Default: the first group's autos in
    order, stopping at the first repeat."""
    combos = [c for c in d["groups"][0]["combos"] if c["kind"] == "auto" and len(c["clips"]) == 1
              and c["clips"][0] in d["clips"]]
    if tags:
        combos = [next(c for c in combos if c["tag"] == t) for t in tags]
    t, hits, strikes, seen = 0.0, [], [], set()
    for c in combos:
        name = c["clips"][0]
        if name in seen and not tags:
            break
        seen.add(name)
        clip = d["clips"][name]
        strikes.append((c["tag"], round(t, 3)))
        hits += clip_hits(clip, t)
        t += clip["combo"][1]
    return {"period": round(t, 3), "strikes": strikes, "hits": hits}


def _hitname(gd, hid):
    if not hid or gd is None:
        return ""
    r = gd.table("HitDamage").get(str(hid))
    if not r:
        return " (not in HitDamage)"
    bucket = {1: "auto", 2: "skill", 3: "ult", 7: "minion"}.get(r.get("DamageType"), f"type{r.get('DamageType')}")
    return f" [{bucket}]"


def _render_prefab(p, gd, indent, lines):
    if not p:
        return
    head = []
    for part in p.get("parts", []):
        c = part["class"]
        if c == "AdventureBullet":
            head.append(f"bullet speed {part.get('moveSpeed')} accel {part.get('acceleratedVelocity', 0)} "
                        f"life {part.get('lifeTime')}" + (f" hit {part['hitDamageId']}{_hitname(gd, part['hitDamageId'])}"
                                                          if part.get("hitDamageId", 1000001) != 1000001 else ""))
        elif c == "AreaEffectEntity":
            head.append(f"area {part.get('duration')} s" + (f" tag {part['areaTag']}" if part.get("areaTag") else ""))
        elif "hitDamageId" in part:
            iv = part.get("hitInterval")
            head.append(f"hit {part['hitDamageId']}{_hitname(gd, part['hitDamageId'])} delay {part.get('hitDelay', 0)}"
                        + (f" every {iv}" if iv and iv < 90 else ""))
        elif c not in ("WeaponFeaturePenetratingObstacle",):
            extra = {k: v for k, v in part.items() if k not in ("class", "spawns")}
            head.append(c.replace("AreaEffect_", "").replace("Component", "") + (f" {extra}" if extra else ""))
    lines.append(f"{indent}{p.get('name') or p.get('ref')}: " + "; ".join(head))
    for part in p.get("parts", []):
        for s in part.get("spawns", []):
            _render_prefab(s, gd, indent + "  -> ", lines)


def render(d: dict, gd=None) -> str:
    lines = [f"char {d['char']}  (times in s from the clip's start, at 1x speed)"]
    for g in d["groups"]:
        lines.append(f"\n{g['name']}" + "".join(f"  {k}: {g[k]}" for k in ("reload", "aimStart", "aim", "reload_other") if k in g))
        for c in g["combos"]:
            lines.append(f"  {c['kind']:6s} {c['tag'] or '-':22s} keys {c['keys']}  {' + '.join(x.replace('ComboClip_', '') for x in c['clips'])}")
    for name, c in sorted(d["clips"].items()):
        lines.append(f"\n{name}: {c['duration']} s (len {c['length']} / speed {c['speed']}), "
                     f"combo window {c['combo'][0]}-{c['combo'][1]}, skill cancel {c['skill_cancel']}"
                     + (f", exit {c['exit']}" if "exit" in c else ""))
        for e in c["events"]:
            s = f"  {e['at']:6.3f}{'-' + format(e['until'], '.3f') if 'until' in e else ''} {e['type']}"
            if e.get("hit"):
                s += f" {e['hit']}{_hitname(gd, e['hit'])}"
            if e.get("detect_interval"):
                s += f" every {e['detect_interval']}"
            if e.get("count", 1) > 1:
                s += f" x{e['count']}"
            for k in ("name", "tag"):
                if e.get(k) and not e[k].startswith("fx_"):
                    s += f" {e[k]!r}"
            if e.get("buffs"):
                s += f" buffs {e['buffs']}"
            lines.append(s)
            _render_prefab(e.get("prefab"), gd, "         ", lines)
    if d["script_weapons"]:
        lines.append("\nspawned by scripts (Lua; timing from the clip's script events):")
        for n, p in d["script_weapons"].items():
            _render_prefab(p, gd, "  ", lines)
    return "\n".join(lines)


def all_chars() -> list[int]:
    ids = set()
    for d in BUNDLE_DIRS:
        if d.is_dir():
            for p in d.iterdir():
                m = re.match(r"char_(\d{3})01_combos\.unity3d$", p.name)
                if m:
                    ids.add(int(m.group(1)))
    return sorted(ids)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m ssr.frames")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("chars", nargs="*", type=int)
    a = ap.parse_args(argv)
    CACHE.mkdir(parents=True, exist_ok=True)
    for cid in a.chars or all_chars():
        d = extract(cid)
        (CACHE / f"{cid}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{cid}: {len(d['clips'])} clips, {len(d['script_weapons'])} script weapons")


if __name__ == "__main__":
    main()
