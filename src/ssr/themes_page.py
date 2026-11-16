"""Emblem themes results as one self-contained HTML page (`python -m ssr.themes` writes it), in the finder page's
style: a table of themes (% vs the control) and each theme's build below."""
from __future__ import annotations

from html import escape
from types import SimpleNamespace

from .finder_page import CSS, _build


def _order(rows):
    ok = sorted((r for r in rows if r.total is not None and r.error is None), key=lambda r: -r.total)
    return ok + [r for r in rows if r.error is not None] + [r for r in rows if r.skipped]


def render_html(rows, title: str, settings: list[str]) -> str:
    """rows: ThemeRows as run_themes returns them."""
    control = next((r.total for r in rows if r.theme == "Control" and r.total), None)
    ok = [r for r in rows if r.total is not None and r.error is None]
    best = max((r.total for r in ok), default=0) or 1
    out = ['<div class="scroll"><table><thead><tr>',
           "".join(f"<th>{c}</th>" for c in ("Theme", "% vs Control", "Raw Damage", "Forced on", "Pinks")),
           "</tr></thead><tbody>"]
    for r in _order(rows):
        forced = ", ".join(escape(r.names[i]) for i in r.members) or '<span class="muted">-</span>'
        pinks = "<br>".join(f"{escape(r.names[k])}: {' · '.join(escape(p) for p in ps)}"
                            for k, ps in enumerate(r.pinks)) or '<span class="muted">-</span>'
        if r.skipped:
            dmg = '<td class="muted" colspan="2">skipped: no member deals this damage type</td>'
        elif r.error is not None:
            dmg = f'<td class="err" colspan="2">{escape(r.error)}</td>'
        else:
            pct = 100 * r.total / control if control else 0
            dmg = (f'<td class="pct"><span class="n">{pct:.2f}%</span><span class="bar">'
                   f'<span style="width:{100 * r.total / best:.2f}%"></span></span></td>'
                   f'<td class="raw">{r.total:,.0f}</td>')
        out.append(f'<tr><td class="rank">{escape(r.theme)}</td>{dmg}<td>{forced}</td>'
                   f'<td class="small">{pinks}</td></tr>')
    out.append("</tbody></table></div>")
    parts = [f"<h1>{escape(title)}</h1>"] + [f'<div class="small muted">{escape(s)}</div>' for s in settings]
    parts += ["<h2>Themes</h2>",
              '<div class="small muted">Each theme forces its emblem lines on every member who deals that damage '
              "type, then re-picks pinks, optimizes potentials and fills the other emblem lines around them.</div>",
              "".join(out)]
    built = [r for r in _order(rows) if r.doc and r.error is None]
    if built:
        cards = [_build(n, SimpleNamespace(members=[r.theme], doc=r.doc, method=r.method))
                 for n, r in enumerate(built, 1)]
        parts += ["<h2>Builds</h2>", '<div class="builds">', "".join(cards), "</div>"]
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>\n")
