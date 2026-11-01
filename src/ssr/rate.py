"""Rating pipeline: discs -> emblems -> reference build -> potentials (design doc, Pipeline)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .data import GameData
from .effects import disc_modifiers
from .game import potential_pools
from .kit import resolve_potential
from .sim import SimResult, simulate
from .emblems import line_relevant
from .stats import ELEM_PEN_BASE
from .team import FILLER, Build, EmblemLine, EmblemSkillLevel, TeamConfig, emblem_lines

ALL_FILLER = ([(FILLER, 6)] * 3, [(FILLER, 6)] * 3)


def gain(base: SimResult, new: SimResult) -> float:
    return new.total / base.total - 1.0 if base.total else 0.0


# ---------------------------------------------------------------- discs

@dataclass
class DiscRow:
    disc_id: int
    name: str
    main_c1: float
    main_c6: float
    support_c1: float
    support_c6: float
    notes: list[str] = field(default_factory=list)


def rate_discs(gd: GameData, team: TeamConfig, disc_ids: list[int] | None = None, build: Build | None = None) -> list[DiscRow]:
    build = build or Build()
    if disc_ids is None:
        disc_ids = sorted(int(k) for k, v in gd.table("Disc").items() if v.get("Available") and v.get("Visible"))
    base = simulate(gd, team, build, emblems=False, discs=ALL_FILLER)
    fill = (FILLER, 6)
    rows = []
    for d in disc_ids:
        vals = {}
        unknown: set[str] = set()
        for c in (1, 6):
            r_main = simulate(gd, team, build, emblems=False, discs=([(d, c), fill, fill], [fill] * 3))
            r_sup = simulate(gd, team, build, emblems=False, discs=([fill] * 3, [(d, c), fill, fill]))
            vals[("main", c)] = gain(base, r_main)
            vals[("support", c)] = gain(base, r_sup)
            unknown |= {u for u in r_main.unknown_modifiers if str(d) in u}
        decode_notes = disc_modifiers(gd, d, 1)[1]
        rows.append(DiscRow(d, gd.item_name(d), vals[("main", 1)], vals[("main", 6)],
                            vals[("support", 1)], vals[("support", 6)], decode_notes + sorted(unknown)))
    rows.sort(key=lambda r: -r.main_c1)
    return rows


# ---------------------------------------------------------------- emblems

@dataclass
class EmblemRow:
    member: int
    char_id: int
    line_name: str
    personal: float
    team: float
    notes: list[str] = field(default_factory=list)


def rate_emblems(gd: GameData, team: TeamConfig, build: Build, members: list[int] | None = None) -> list[EmblemRow]:
    base = simulate(gd, team, build, emblems=False)
    rows = []
    lines = emblem_lines(gd)
    for i, m in enumerate(team.members):
        if members is not None and i not in members:
            continue
        element = gd.table("Character")[str(m.char_id)]["EET"]
        for line in lines:
            if not line_relevant(line, element, m.role):
                continue
            r = simulate(gd, team, build, emblems=False, extra=[(i, line)])
            rows.append(EmblemRow(i, m.char_id, line.name,
                                  r.by_member.get(i, 0) / base.by_member[i] - 1 if base.by_member.get(i) else 0.0,
                                  gain(base, r)))
            if isinstance(line, EmblemLine) and ELEM_PEN_BASE <= line.stat < ELEM_PEN_BASE + 6:
                r2 = simulate(gd, team, build, emblems=False, extra=[(i, line), (i, line)])
                rows.append(EmblemRow(i, m.char_id, f"{line.name} (2nd line)",
                                      r2.by_member.get(i, 0) / r.by_member[i] - 1 if r.by_member.get(i) else 0.0,
                                      gain(r, r2), ["gain of a second line on top of the first"]))
    return rows


# ---------------------------------------------------------------- potentials

def _candidates(gd: GameData, team: TeamConfig, i: int) -> list[tuple[int, str]]:
    m = team.members[i]
    pools = potential_pools(gd, m.char_id, m.role)
    return [(p, "normal") for p in pools["normal"]] + [(p, "common") for p in pools["common"]]


def build_reference(gd: GameData, team: TeamConfig, base: Build) -> Build:
    ref = base
    cfg = team.reference
    lv = int(cfg.get("level", 6))
    for _ in range(int(cfg.get("steps", 2))):
        cur = simulate(gd, team, ref)
        picks = []
        for i, m in enumerate(team.members):
            n_pick = int(cfg.get("main_picks", 2) if m.role == "main" else cfg.get("support_picks", 1))
            scored = []
            for p, _kind in _candidates(gd, team, i):
                if (m.char_id, p) in ref.potentials:
                    continue
                scored.append((gain(cur, simulate(gd, team, ref.with_potential(m.char_id, p, lv))), p))
            scored.sort(key=lambda x: (-x[0], x[1]))
            picks += [(m.char_id, p) for _, p in scored[:n_pick]]
        for cid, p in picks:
            ref = ref.with_potential(cid, p, lv)
    return ref


@dataclass
class PotRow:
    member: int
    char_id: int
    potential_id: int
    name: str
    kind: str
    in_reference: bool
    gains: list[float]
    notes: list[str] = field(default_factory=list)


def rate_potentials(gd: GameData, team: TeamConfig, ref: Build, levels=range(1, 10),
                    only: list[tuple[int, int]] | None = None) -> list[PotRow]:
    rows = []
    ref_result = simulate(gd, team, ref)
    removed_cache: dict = {}
    for i, m in enumerate(team.members):
        for p, kind in _candidates(gd, team, i):
            if only is not None and (m.char_id, p) not in only:
                continue
            in_ref = (m.char_id, p) in ref.potentials
            if in_ref:
                base_build = ref.without(m.char_id, p)
                if (m.char_id, p) not in removed_cache:
                    removed_cache[(m.char_id, p)] = simulate(gd, team, base_build)
                base = removed_cache[(m.char_id, p)]
            else:
                base_build, base = ref, ref_result
            gains = []
            unknown: set[str] = set()
            for lv in levels:
                r = simulate(gd, team, base_build.with_potential(m.char_id, p, lv))
                gains.append(gain(base, r))
                unknown |= {u for u in r.unknown_modifiers if f"({p})" in u}
            rp = resolve_potential(gd, m.kit, p, 6)
            notes = list(dict.fromkeys(rp.notes + sorted(unknown)))
            if all(abs(g) < 1e-12 for g in gains):
                why = "no simulated damage value"
                if not rp.modifiers and not rp.add_hits:
                    why += " (utility/behaviour only, or not modelled)"
                elif rp.modifiers and all(mm.stat in (2,) for mm in rp.modifiers):
                    why += " (DEF only)"
                else:
                    why += " (depends on something not in this build, or a stat with no effect here)"
                notes.insert(0, why)
            rows.append(PotRow(i, m.char_id, p, gd.item_name(p), kind, in_ref, gains, notes))
    return rows
