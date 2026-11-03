"""Static catalogue for the page: spec'd trekkers with their pinks/potentials, discs, emblem lines."""
from __future__ import annotations

from ..data import GameData
from ..effects import disc_modifiers
from ..emblems import emblem_options
from ..enemies import preset_catalog
from ..game import potential_pools, talent_groups
from ..kit import SPECS
from ..stats import ELEMENTS

ROWS = {1: "Main Build 1", 2: "Main Build 2", 3: "Generic"}


def _potential(gd: GameData, pid: int, kind: str | None = None) -> dict:
    p = gd.table("Potential").get(str(pid), {})
    rarity = gd.table("Item").get(str(pid), {}).get("Rarity", 2)
    out = {"id": pid, "name": gd.item_name(pid), "row": p.get("Build", 3), "rarity": rarity}
    if kind:
        out["kind"] = kind
    return out


def trekker_ids() -> list[int]:
    return sorted(int(p.stem) for p in SPECS.glob("*.yaml") if p.stem.isdigit())


def catalog(gd: GameData) -> dict:
    trekkers, emblems = [], {}
    for cid in trekker_ids():
        if str(cid) not in gd.table("Character"):
            continue
        roles = {}
        for role in ("main", "support"):
            pools = potential_pools(gd, cid, role)
            roles[role] = {
                "pinks": [_potential(gd, p) for p in pools["pink"]],
                # in-game preset order within a row: rarity (purple first), then id; the game also floats
                # higher target levels first, which the page doesn't do (cards would jump on every click)
                "potentials": sorted([_potential(gd, p, "normal") for p in pools["normal"]]
                                     + [_potential(gd, p, "common") for p in pools["common"]],
                                     key=lambda x: (x["row"], x["rarity"], x["id"])),
            }
        el = gd.table("Character")[str(cid)].get("EET", 0)
        trekkers.append({"id": cid, "name": gd.char_name(cid), "element": ELEMENTS.get(el, "?"),
                         "talents": len(talent_groups(gd, cid)), "roles": roles})
        emblems[str(cid)] = [{"name": o.name, "kind": o.kind, "slots": sorted(o.slots),
                              "tiers": [{"label": t.label, "colour": t.colour} for t in o.tiers]}
                             for o in emblem_options(gd, cid)]
    discs = []
    for k, v in gd.table("Disc").items():
        if not (v.get("Available") and v.get("Visible")):
            continue
        did = int(k)
        notes = disc_modifiers(gd, did, 1)[1]
        discs.append({"id": did, "name": gd.item_name(did), "element": ELEMENTS.get(v.get("EET", 0), "Neutral"),
                      "modelled": not any("not modelled" in n for n in notes)})
    discs.sort(key=lambda d: d["name"])
    trekkers.sort(key=lambda t: t["name"])
    return {"trekkers": trekkers, "discs": discs, "emblems": emblems, "enemies": preset_catalog(gd)}
