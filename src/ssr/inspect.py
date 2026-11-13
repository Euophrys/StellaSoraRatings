"""Dump what the game data says about a Trekker or disc, for writing kit / disc specs.

    python -m ssr.inspect trekker "Snowish Laru" support   # skills, hits, all potential pools
    python -m ssr.inspect trekker Amber main --level 6     # potential Params resolved at Lv6
    python -m ssr.inspect hits 158                         # every HitDamage row of char 158
    python -m ssr.inspect disc "Fireworks"                 # melody/harmony text, Params, decoded modifiers
    python -m ssr.inspect scripted-discs --element 2       # discs with scripted parts and no spec
    python -m ssr.inspect word "Butterfly Mark"            # keyword (Word table) text and Params
    python -m ssr.inspect frames Ann                       # animation frame data (python -m ssr.frames extract first)
"""
from __future__ import annotations

import argparse
import re

from .data import GameData
from .effects import disc_modifiers, potential_modifiers
from .game import potential_pools, skill_cd, skill_ids, ult_energy
from .refs import resolve

ELEMENTS = {1: "Aqua", 2: "Ignis", 3: "Terra", 4: "Ventus", 5: "Lux", 6: "Umbra", 7: "neutral"}
CLASSES = {1: "Vanguard", 2: "Versatile", 3: "Support"}


def _val(gd, ref, level):
    if not isinstance(ref, str) or "," not in ref:
        return ref
    if ref.startswith("HitDamage"):
        return ref   # a hit id; see `hits`
    try:
        v = resolve(gd, ref, level).value
        return round(v, 4) if isinstance(v, float) else v
    except Exception as e:  # missing rows are common (e.g. ScriptParameterValue ids that don't exist)
        return f"ERR {e}"


def _params(gd, row, level, indent="      "):
    for k, v in row.items():
        if k.startswith("Param") and v:
            print(f"{indent}{k:8s} {v}  =>  {_val(gd, v, level)}")


def _char(gd, name):
    try:
        return int(name)
    except ValueError:
        return gd.find_char(name)


def trekker(gd, name, roles, level):
    cid = _char(gd, name)
    c = gd.table("Character")[str(cid)]
    print(f"{gd.char_name(cid)} ({cid}): {ELEMENTS.get(c.get('EET'))}, class {c.get('Class')} "
          f"{CLASSES.get(c.get('Class'), '')}, EnergyConvRatio {c.get('EnergyConvRatio')}")
    for role in roles:
        print(f"\n===== {role}")
        for slot, sid in skill_ids(gd, cid, role).items():
            r = gd.table("Skill").get(str(sid), {})
            print(f"--- {slot} {sid} {gd.text(f'Skill.{sid}.1')}  CD {skill_cd(gd, sid)} s  "
                  f"ult energy {ult_energy(gd, sid)}  GetEnergyLimit {r.get('GetEnergyLimit')}")
            print("   ", gd.text(f"Skill.{sid}.2"))
            _params(gd, r, 10)
        pools = potential_pools(gd, cid, role)
        for kind in ("pink", "normal", "common"):
            for p in pools[kind]:
                lv = 1 if kind == "pink" else level
                print(f"\n  [{kind}] {p} {gd.item_name(p)}  (Lv{lv})")
                print("     ", (gd.text(f"Potential.{p}.2") or "").replace("\n", " "))
                _params(gd, gd.table("Potential")[str(p)], lv)
                mods, notes = potential_modifiers(gd, p, lv)
                for i, m in enumerate(mods):
                    t = m.trigger
                    print(f"      mod {i}: {m.label()} {m.value:g} -> {m.target}"
                          + (f"  trigger {t.event} {t.duration:g}s x{t.max_stacks}" if t else "  always")
                          + ("  NEEDS hit_tags" if m.needs_scope else ""))
                for n in notes:
                    print("      note:", n)


def hits(gd, name):
    cid = _char(gd, name)
    for k, r in gd.table("HitDamage").items():
        if k.startswith(str(cid)) and len(k) == 9:
            pct = [round(x * 1e-4, 1) for x in r.get("SkillPercentAmend", [])][:10]
            print(k, f"DamageType {r.get('DamageType')}", f"element {r.get('ElementType')}",
                  "HP" if r.get("DamageBonusType") == 3 else "ATK", f"energy {r.get('EnergyCharge')}",
                  f"level {r.get('levelTypeData')}/{r.get('LevelData')}", f"% {pct}")


def _disc_id(gd, name):
    try:
        return int(name)
    except ValueError:
        return gd.find_item(name, within="Disc")


def _parts(gd, d, level=1):
    out = [("melody", r) for r in gd.table("MainSkill").values()
           if r.get("GroupId") == d.get("MainSkillGroupId") and r.get("Level") == level]
    for key, g in (("harmony1", "SecondarySkillGroupId1"), ("harmony2", "SecondarySkillGroupId2")):
        out += [(key, r) for r in gd.table("SecondarySkill").values()
                if r.get("GroupId") == d.get(g) and r.get("Level") == 1]
    return out


def _clean(t):
    return re.sub(r"<[^>]+>|##([^#]+)#\d+#", lambda m: m.group(1) or "", t or "")


def disc(gd, name):
    did = _disc_id(gd, name)
    d = gd.table("Disc")[str(did)]
    print(f"{gd.item_name(did)} ({did}): {ELEMENTS.get(d.get('EET'))}")
    for key, row in _parts(gd, d):
        print(f"  {key}: EffectId {row.get('EffectId')}\n    {_clean(gd.text(row.get('Desc', '')))}")
        print("    ", {k: v for k, v in row.items() if k.startswith("Param")})
    mods, notes = disc_modifiers(gd, did, 1)
    print("  decoded (C1):")
    for m in mods:
        t = m.trigger
        print(f"    {m.label()} {m.value:g} -> {m.target}" + (f"  trigger {t.event} {t.duration:g}s x{t.max_stacks}" if t else "  always")
              + f"   [{m.source}]")
    for n in notes:
        print("    note:", n)


def scripted_discs(gd, element):
    for k, d in sorted(gd.table("Disc").items()):
        if not (d.get("Available") and d.get("Visible")):
            continue
        if element and d.get("EET") not in (element, 7):
            continue
        _, notes = disc_modifiers(gd, int(k), 1)
        bad = [n for n in notes if "not modelled" in n or "no damage model" in n]
        if bad:
            print(f"{k} {gd.item_name(int(k))} [{ELEMENTS.get(d.get('EET'))}]")
            for n in bad:
                print("   ", n.split(": ", 1)[-1] if ": " in n else n)


def word(gd, name):
    for k, r in gd.table("Word").items():
        if (gd.text(r.get("Title", "")) or "").lower() == name.lower() or k == name:
            print(k, gd.text(r.get("Title", "")), "|", _clean(gd.text(r.get("Desc", ""))))
            _params(gd, r, 1, "    ")


def frames(gd, name):
    from . import frames as fr
    cid = _char(gd, name)
    d = fr.load(cid)
    if d is None:
        raise SystemExit(f"no frame data for {cid}: run python -m ssr.frames extract {cid}")
    print(gd.char_name(cid), end=": ")
    print(fr.render(d, gd))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ssr.inspect")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trekker"); t.add_argument("name"); t.add_argument("roles", nargs="*", default=["main", "support"])
    t.add_argument("--level", type=int, default=6)
    sub.add_parser("hits").add_argument("name")
    sub.add_parser("disc").add_argument("name")
    s = sub.add_parser("scripted-discs"); s.add_argument("--element", type=int, default=0)
    sub.add_parser("word").add_argument("name")
    sub.add_parser("frames").add_argument("name")
    a = ap.parse_args(argv)
    gd = GameData()
    if a.cmd == "trekker":
        trekker(gd, a.name, a.roles, a.level)
    elif a.cmd == "hits":
        hits(gd, a.name)
    elif a.cmd == "disc":
        disc(gd, a.name)
    elif a.cmd == "scripted-discs":
        scripted_discs(gd, a.element)
    elif a.cmd == "word":
        word(gd, a.name)
    elif a.cmd == "frames":
        frames(gd, a.name)


if __name__ == "__main__":
    main()
