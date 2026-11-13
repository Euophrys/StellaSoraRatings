"""The team finder's results as one self-contained HTML page (`python -m ssr.finder` writes it).

Same tables as the build guide's Find teams section: Optimized (finalists, full totals) above Screened (every team,
screen totals), so a full total is never compared with a screen total. Each finalist's build is listed below.
"""
from __future__ import annotations

from html import escape

SLOT_LEVEL = {1: 70, 2: 80, 3: 90}

CSS = """
:root { --bg: #f7f7f9; --panel: #ffffff; --text: #1d1f24; --muted: #6b7080; --border: #d5d8df; --neg: #c63a3a;
  --th-bg: #2d4a6b; --th-text: #ffffff; --row-alt: #e9eef5; --bar: #d4aa6a; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #15171c; --panel: #1e2128; --text: #e6e8ee; --muted: #9298a8; --border: #363b47; --neg: #ff7a7a;
    --th-bg: #24364d; --th-text: #e6e8ee; --row-alt: #232831; --bar: #b8904f; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 8px 16px 48px; }
h1 { font-size: 22px; margin: 18px 0 4px; }
h2 { font-size: 17px; margin: 26px 0 4px; }
.muted { color: var(--muted); }
.small { font-size: 12px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 760px; font-size: 13px; background: var(--panel); }
th { background: var(--th-bg); color: var(--th-text); padding: 7px 8px; text-align: center; border: 1px solid var(--border); }
td { padding: 5px 8px; border: 1px solid var(--border); vertical-align: middle; }
tbody tr:nth-child(even) td { background: var(--row-alt); }
td.rank { font-weight: 600; white-space: nowrap; }
td.pct { white-space: nowrap; font-weight: 600; font-variant-numeric: tabular-nums; }
td.pct .n { display: inline-block; width: 4.6em; text-align: right; margin-right: 6px; }
.bar { display: inline-block; width: 140px; height: 18px; vertical-align: middle; }
.bar span { display: block; height: 100%; background: var(--bar); }
td.raw { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.who .name { font-weight: 600; }
td.err { color: var(--neg); }
.builds { display: grid; gap: 12px; }
.build { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; }
.build h3 { margin: 0 0 6px; font-size: 14px; }
.members { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
@media (max-width: 800px) { .members { grid-template-columns: 1fr; } }
.members ul { margin: 4px 0 0; padding-left: 18px; }
"""


def _member_cell(r, k: int) -> str:
    role = "Main" if k == 0 else "Support"
    pinks = " · ".join(escape(p) for p in (r.pinks[k] if k < len(r.pinks) else []))
    return (f'<td class="who"><div class="name">{escape(r.members[k])}</div>'
            f'<div class="small muted">{role}</div><div class="small muted">{pinks}</div></td>')


def _table(rows, value) -> str:
    vals = [value(r) for r in rows if r.error is None and value(r) is not None]
    best = max(vals, default=0) or 1
    out = ['<div class="scroll"><table><thead><tr>',
           "".join(f"<th>{c}</th>" for c in ("Team", "Damage %", "Raw Damage", "Main", "Support 1", "Support 2")),
           "</tr></thead><tbody>"]
    for n, r in enumerate(rows, 1):
        v = value(r)
        if r.error is not None or v is None:
            dmg = f'<td class="err" colspan="2">{escape(r.error or "no total")}</td>'
        else:
            pct = 100 * v / best
            dmg = (f'<td class="pct"><span class="n">{pct:.2f}%</span>'
                   f'<span class="bar"><span style="width:{pct:.2f}%"></span></span></td>'
                   f'<td class="raw">{v:,.0f}</td>')
        out.append(f'<tr><td class="rank">#{n}</td>{dmg}{"".join(_member_cell(r, k) for k in range(3))}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def _build(n: int, r) -> str:
    cols = []
    for k, m in enumerate((r.doc or {}).get("members") or []):
        targets = [f"{escape(name)} Lv{lv}" for name, lv in (m.get("targets") or {}).items() if lv]
        emblems = [f"Lv{SLOT_LEVEL.get(e['slot'], '?')}: " + ", ".join(
            f"{escape(str(ln['line']))} ({escape(str(ln['tier']))})" for ln in e.get("lines") or [])
            for e in m.get("emblems") or [] if isinstance(e, dict)]
        items = "".join(f"<li>{t}</li>" for t in targets) or '<li class="muted">no potentials</li>'
        em = "".join(f'<div class="small">{e}</div>' for e in emblems)
        cols.append(f'<div><div class="name"><b>{escape(str(m.get("trekker", "")))}</b> '
                    f'<span class="small muted">{"Main" if k == 0 else "Support"}</span></div><ul>{items}</ul>{em}</div>')
    method = f' <span class="small muted">{escape(r.method)}</span>' if r.method else ""
    return f'<div class="build"><h3>#{n} {escape(" / ".join(r.members))}{method}</h3><div class="members">{"".join(cols)}</div></div>'


def render_html(rows, title: str, settings: list[str]) -> str:
    """rows: FinderRows as find_teams returns them (finalists first)."""
    finalists = [r for r in rows if r.finalist and r.error is None]
    screened = sorted((r for r in rows if r.error is None), key=lambda r: -(r.screen_total or 0)) \
        + [r for r in rows if r.error is not None]
    parts = [f"<h1>{escape(title)}</h1>"] + [f'<div class="small muted">{escape(s)}</div>' for s in settings]
    parts.append("<h2>Optimized</h2>")
    if finalists:
        parts += ['<div class="small muted">Full build: optimize with the template\'s budget, then greedy emblems.</div>',
                  _table(finalists, lambda r: r.total)]
    else:
        parts.append('<div class="small muted">No finalists.</div>')
    parts += ["<h2>Screened</h2>",
              '<div class="small muted">Every team: pinks on the reference build, then potentials straight to Lv6. '
              "Ranks the teams; only the top ones get the full build.</div>",
              _table(screened, lambda r: r.screen_total)]
    if finalists:
        parts += ["<h2>Finalist builds</h2>", '<div class="builds">',
                  "".join(_build(n, r) for n, r in enumerate(finalists, 1)), "</div>"]
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>\n")
