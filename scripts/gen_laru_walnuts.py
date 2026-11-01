# Prints the Walnut / General Curly hit schedules used in specs/trekkers/158.yaml (paste into the skill hits,
# Investiture Ceremony and Heart's Benediction add_hits). Run: python scripts/gen_laru_walnuts.py
# Laru support timeline (user, YouTube @23 fps): shells land at +0.7 s, then every 2 s (4 base, +2 with Two-Gun Salute).
# Walnut per shell (spawn = explosion, impact + 0.3 s), attacks 1/s from spawn + 0.5 s; lives ~13.5 s (fitted; x1.5 with
# Heart's Edict), max 4 (the oldest dies when a 5th spawns, including the next cast's).
# Promotion Time: when the 4th Walnut spawns, the 4 merge into General Curly (lives like a Walnut, attacks 1/s).
TGS, EDICT, PT, INV, BEN = 515825, 515829, 515823, 515824, 515828
CD = 18.0
def shells(tgs): return [0.7 + 2 * k for k in range(6 if tgs else 4)]
def gate(tgs, edict, extra_req=(), extra_exc=()):
    req = [TGS] if tgs else []
    req += [EDICT] if edict else []
    exc = ([] if tgs else [TGS]) + ([] if edict else [EDICT])
    req += list(extra_req); exc += list(extra_exc)
    g = {}
    if len(req) == 1: g["requires"] = req
    elif req: g["requires_all"] = req
    if exc: g["excludes"] = exc
    return g
def fmt(d):
    parts = []
    for k, v in d.items():
        if isinstance(v, list): v = "[" + ", ".join(str(x) for x in v) + "]"
        elif isinstance(v, float): v = f"{v:g}"
        parts.append(f"{k}: {v}")
    return "- {" + ", ".join(parts) + "}"
LIFE = 13.5   # fitted to the user's video: all 4 still out at the next cast, dying just before replacements

def windows(tgs, edict, pt):
    """[(kind, start, end)]: minion windows. Walnuts outlive the next cast (CD 18 s); a 5th spawn, counting the
    next cycle's, kills the oldest."""
    life = LIFE * (1.5 if edict else 1.0)
    sp = [s + 0.3 for s in shells(tgs)]
    seq = sp + [s + CD for s in sp] + [s + 2 * CD for s in sp]
    out = []
    if pt:
        merge = sp[3]
        for s in sp[:3]: out.append(("walnut", s, merge))
        out.append(("curly", merge, merge + life))
        for s in sp[4:]: out.append(("walnut", s, s + life))
        return out
    for i, s in enumerate(sp):
        out.append(("walnut", s, min(s + life, seq[i + 4])))
    return out
def ticks(start, end, first, step):
    t, n = start + first, 0
    while t < end - 1e-9: n += 1; t += step
    return n
lines = {"base": [], INV: [], BEN: []}
for tgs in (False, True):
    for edict in (False, True):
        for pt in (False, True):
            g = gate(tgs, edict, [PT] if pt else [], [] if pt else [PT])
            for kind, s, e in windows(tgs, edict, pt):
                if kind == "walnut":
                    n = ticks(s, e, 0.5, 1.0)
                    if n: lines["base"].append(fmt({"hit": 158320003, "count": n, "offset": round(s + 0.5, 3), "interval": 1.0, "tags": "[walnut, minion]", **g}))
                    n = ticks(s, e, 0.0, 1.0)   # Heart's Benediction aura 1/s
                    if n: lines[BEN].append(fmt({"hit": 158528001, "count": n, "offset": round(s + 1.0, 3), "interval": 1.0, "tags": "[walnut, minion]", **g}))
                    n = ticks(s, e, 4.0, 4.0)   # Investiture: Walnut skill every 4 s
                    if n: lines[INV].append(fmt({"hit": 158524001, "count": n, "offset": round(s + 4.0, 3), "interval": 4.0, "tags": "[walnut_skill, minion]", **g}))
                else:
                    n = ticks(s, e, 0.2, 1.0)
                    lines["base"].append(fmt({"hit": 158523001, "count": n, "offset": round(s + 0.2, 3), "interval": 1.0, "tags": "[curly, minion]", **g}))
                    n = ticks(s, e, 0.0, 0.5)
                    lines[BEN].append(fmt({"hit": 158528002, "count": n, "offset": round(s + 0.5, 3), "interval": 0.5, "tags": "[curly, minion]", **g}))
                    k = ticks(s, e, 4.0, 4.0)
                    for j in range(k):
                        lines[INV].append(fmt({"hit": 158524002, "count": 6, "offset": round(s + 4.0 + 4 * j, 3), "interval": 0.15, "tags": "[curly, curly_skill, minion]", **g}))
for k, v in lines.items():
    print(f"### {k}")
    for l in v: print("          " + l)
