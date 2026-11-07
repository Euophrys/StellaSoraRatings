"""Authored-but-untimed kits: every one loads, simulates, and leaves nothing to the 100% uptime default."""
import re
from pathlib import Path

import pytest
import yaml

from ssr.game import potential_pools
from ssr.kit import SPECS, resolve_potential, role_status
from ssr.sim import simulate
from ssr.team import Build, team_from_doc

BUCKETS = {"auto_dmg", "skill_dmg", "ult_dmg", "mark_dmg", "other_dmg", "minion_dmg", "any"}
PARTNERS = {2: ("Amber", ["Flora", "Chixia"]), 5: ("Firstlight Noya", ["Tilia", "Firefly"]),
            1: ("Chitose", ["Freesia", "Teresa"]), 3: ("Gerie", ["Ridge", "Nazuna"]),
            6: ("Mistique", ["Cosette", "Flora"]), 4: ("Noya", ["Canace", "Ann"])}


def _untimed():
    out = []
    for p in sorted(SPECS.glob("*.yaml")):
        for role in ("main", "support"):
            if role_status(p, role) == "untimed":
                out.append((int(p.stem), role))
    return out


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _team(gd, cid, role, talents=0):
    name = gd.char_name(cid)
    main, sup = PARTNERS[gd.table("Character")[str(cid)]["EET"]]
    sup = [s for s in sup if s != name]
    if role == "main":
        members = [{"trekker": name, "role": "main", "talents": talents}]
        members += [{"trekker": s, "role": "support"} for s in sup[:2]]
    else:
        members = [{"trekker": "Amber" if main == name else main, "role": "main"},
                   {"trekker": name, "role": "support", "talents": talents}]
        members += [{"trekker": s, "role": "support"} for s in sup[:1]]
    return team_from_doc(gd, {"members": members, "discs": {"main": ["filler"] * 3, "support": ["filler"] * 3},
                              "enemy": {"res": 250, "defense": 500}})


@pytest.mark.parametrize("cid,role", _untimed())
def test_kit_names_real_hits_and_tags(gd, cid, role):
    doc = yaml.safe_load(Path(SPECS / f"{cid}.yaml").read_text(encoding="utf-8"))
    sec = doc[role]
    tags = {"mark"} | set((sec.get("mark") or {}).get("tags", ()))
    for d in _walk(sec):
        tags |= set(d.get("tags", ()))
    for d in _walk({"section": sec, "talents": doc.get("talents")}):
        if d.get("hit"):
            assert str(d["hit"]) in gd.table("HitDamage"), f"no HitDamage row {d['hit']}"
        for key in ("event", "when"):
            if isinstance(d.get(key), str):
                for m in re.finditer(r"(?:hit|marker):self:(\w+)", d[key]):
                    assert m.group(1) in tags | BUCKETS, f"{d[key]!r}: no hit has the tag {m.group(1)!r}"
    pools = potential_pools(gd, cid, role)
    pool = set(pools["pink"] + pools["normal"] + pools["common"])
    assert set(int(k) for k in sec.get("potentials") or {}) <= pool
    for p in sec.get("procs") or []:
        assert not (set(p.get("tags", ())) & set(re.findall(r"hit:self:(\w+)", p["event"]))), f"{p} re-triggers itself"


@pytest.mark.parametrize("cid,role", _untimed())
def test_no_potential_runs_on_an_assumed_trigger(gd, cid, role):
    team = _team(gd, cid, role)
    member = team.members[0 if role == "main" else 1]
    pools = potential_pools(gd, cid, role)
    for kind in ("pink", "normal", "common"):
        for pid in pools[kind]:
            lv = 1 if kind == "pink" else 6
            for m in resolve_potential(gd, member.kit, pid, lv).modifiers:
                assert not m.needs_scope, f"{pid} {gd.item_name(pid)}: {m.label()} has no hit scope"
                assert not (m.trigger and m.trigger.event == "unknown" and m.trigger.uptime is None), \
                    f"{pid} {gd.item_name(pid)}: {m.label()} has no trigger"


@pytest.mark.parametrize("cid,role", _untimed())
def test_kit_simulates_every_potential_and_talent(gd, cid, role):
    team = _team(gd, cid, role)
    base = simulate(gd, team, Build())
    assert base.total > 0
    pools = potential_pools(gd, cid, role)
    for kind in ("pink", "normal", "common"):
        for pid in pools[kind]:
            lv = 1 if kind == "pink" else 6
            r = simulate(gd, team, Build({(cid, pid): lv}))
            assert r.total < base.total * 4, f"{pid} {gd.item_name(pid)} is suspiciously strong"
    t5 = simulate(gd, _team(gd, cid, role, talents=5), Build())
    assert not [u for u in t5.unknown_modifiers if "key talent" in u and gd.char_name(cid) in u]


def test_untimed_is_a_role_status():
    assert role_status(SPECS / "108.yaml", "main") == "untimed"
    assert role_status(SPECS / "108.yaml", "support") == "untimed"
