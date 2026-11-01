import openpyxl
from ssr.report import write_xlsx
from ssr.rate import rate_discs, rate_emblems, rate_potentials
from ssr.sim import simulate
from ssr.team import Build
from ssr.game import potential_pools


def test_report_sheets_and_rows(gd, team, tmp_path):
    discs = rate_discs(gd, team, disc_ids=[214066, 214038])
    emb = rate_emblems(gd, team, Build(), members=[0])
    pots = rate_potentials(gd, team, Build(), levels=[1, 6])
    out = tmp_path / "r.xlsx"
    write_xlsx(out, gd, team, discs, emb, pots, simulate(gd, team, Build()))
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Potentials", "Discs", "Emblems", "Breakdown", "Assumptions"]
    names = {c.value for c in wb["Potentials"]["A"] if c.value}
    for m in team.members:
        pools = potential_pools(gd, m.char_id, m.role)
        for p in pools["normal"] + pools["common"]:
            assert gd.item_name(p) in names, gd.item_name(p)
    disc_names = {c.value for c in wb["Discs"]["A"]}
    assert "My Guiding Star" in disc_names
