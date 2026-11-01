"""Write ratings to an .xlsx workbook."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill

from .data import GameData, REPO_ROOT
from .rate import DiscRow, EmblemRow, PotRow
from .sim import SimResult
from .team import TeamConfig

PCT = "0.00%"
BOLD = Font(bold=True)
HEAD_FILL = PatternFill("solid", fgColor="DDEBF7")
GROUP_FILL = PatternFill("solid", fgColor="F2F2F2")


def _header(ws, cols):
    ws.append(cols)
    for c in ws[ws.max_row]:
        c.font = BOLD
        c.fill = HEAD_FILL
    ws.freeze_panes = ws.cell(row=ws.max_row + 1, column=2)


def _scale(ws, rng):
    ws.conditional_formatting.add(rng, ColorScaleRule(start_type="min", start_color="FFFFFF",
                                                      end_type="max", end_color="63BE7B"))


def write_xlsx(path: Path, gd: GameData, team: TeamConfig, discs: list[DiscRow], emblems: list[EmblemRow],
               pots: list[PotRow], baseline: SimResult) -> None:
    wb = Workbook()

    # Potentials
    ws = wb.active
    ws.title = "Potentials"
    n_lv = max((len(r.gains) for r in pots), default=9)
    _header(ws, ["Name", "Kind", "In ref"] + [f"Lv{i}" for i in range(1, n_lv + 1)] + ["Notes"])
    for i, m in enumerate(team.members):
        ws.append([f"{gd.char_name(m.char_id)} ({m.role})"])
        for c in ws[ws.max_row]:
            c.font = BOLD
            c.fill = GROUP_FILL
        first = ws.max_row + 1
        for r in sorted((r for r in pots if r.member == i), key=lambda r: -max(r.gains, default=0)):
            ws.append([r.name, r.kind, "yes" if r.in_reference else ""] + r.gains + ["; ".join(r.notes)])
            for c in ws[ws.max_row][3:3 + len(r.gains)]:
                c.number_format = PCT
        last = ws.max_row
        if last >= first:
            _scale(ws, f"D{first}:{chr(ord('D') + n_lv - 1)}{last}")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions[chr(ord("D") + n_lv)].width = 80

    # Discs
    ws = wb.create_sheet("Discs")
    _header(ws, ["Disc", "Main C1", "Main C6", "Support C1", "Support C6", "Notes"])
    for r in discs:
        ws.append([r.name, r.main_c1, r.main_c6, r.support_c1, r.support_c6, "; ".join(r.notes)])
        for c in ws[ws.max_row][1:5]:
            c.number_format = PCT
    if discs:
        _scale(ws, f"B2:C{ws.max_row}")
        _scale(ws, f"D2:E{ws.max_row}")
    ws.column_dimensions["A"].width = 34

    # Emblems
    ws = wb.create_sheet("Emblems")
    _header(ws, ["Trekker", "Line", "Personal", "Team", "Notes"])
    for r in sorted(emblems, key=lambda r: (r.member, -r.personal)):
        ws.append([gd.char_name(r.char_id), r.line_name, r.personal, r.team, "; ".join(r.notes)])
        for c in ws[ws.max_row][2:4]:
            c.number_format = PCT
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 26

    # Breakdown
    ws = wb.create_sheet("Breakdown")
    _header(ws, ["Trekker", "Bucket", "Damage", "Share"])
    for (mi, slot), dmg in sorted(baseline.by_slot.items(), key=lambda kv: (kv[0][0], -kv[1])):
        ws.append([gd.char_name(team.members[mi].char_id), slot, round(dmg), dmg / baseline.total])
        ws[ws.max_row][3].number_format = PCT
    ws.append([])
    ws.append(["Trekker", "Action", "Casts"])
    for c in ws[ws.max_row]:
        c.font = BOLD
    for (mi, a), n in sorted(baseline.casts.items()):
        ws.append([gd.char_name(team.members[mi].char_id), a, n])
    ws.column_dimensions["A"].width = 18

    # Assumptions
    ws = wb.create_sheet("Assumptions")
    ws.append(["Modifiers with assumed uptime or scope (baseline run)"])
    ws[ws.max_row][0].font = BOLD
    for u in baseline.unknown_modifiers:
        ws.append([u])
    ws.append([])
    ws.append([f"Enemy: RES {team.enemy.res:g}, DEF {team.enemy.defense:g}, break x{team.enemy.broken:g}; "
               f"fight {team.fight_length:g} s"])
    ws.append([])
    doc = REPO_ROOT / "docs" / "assumptions.md"
    if doc.exists():
        for line in doc.read_text(encoding="utf-8").splitlines():
            ws.append([line])
    ws.column_dimensions["A"].width = 140
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=False)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
