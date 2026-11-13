import pytest
from ssr.rate import gain, rate_discs, rate_emblems, build_reference, rate_potentials
from ssr.sim import simulate
from ssr.team import Build, FILLER
from ssr.game import potential_pools, disc_base_stats
from ssr.effects import Modifier
from ssr.stats import ATK, HP, StatBlock
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

FILLERS = ([(FILLER, 6)] * 3, [(FILLER, 6)] * 3)


def test_gain():
    class R:  # minimal SimResult stand-in
        def __init__(self, t): self.total = t
    assert gain(R(100), R(110)) == pytest.approx(0.10)


def test_filler_disc_gains_zero(gd, team):
    row = rate_discs(gd, team, disc_ids=[214067])[0]   # filler source disc at C6 has filler stats, but melody/harmony too
    assert row.support_c6 == pytest.approx(0.0, abs=1e-9)


def test_support_slot_ignores_effects(gd, team):
    row = rate_discs(gd, team, disc_ids=[214038])[0]   # Ripples of Nostalgia
    base = simulate(gd, team, Build(), discs=FILLERS)
    rip, fil = disc_base_stats(gd, 214038, copies=1), disc_base_stats(gd, 214067, copies=6)
    extra = []
    for i in range(3):
        extra.append((i, Modifier(stat=ATK, value=rip.flat[ATK] - fil.flat[ATK], source="t")))
        extra.append((i, Modifier(stat=HP, value=rip.flat[HP] - fil.flat[HP], source="t")))
        for st, v in rip.vals.items():
            extra.append((i, Modifier(stat=st, value=v, source="t")))
    manual = simulate(gd, team, Build(), discs=FILLERS, extra=extra)
    assert row.support_c1 == pytest.approx(gain(base, manual), rel=1e-9)
    assert row.main_c1 > row.support_c1   # melody adds value in a main slot


def test_reference_size(gd, team):
    ref = build_reference(gd, team, Build())
    main = [k for k in ref.potentials if k[0] == 162]
    # 2 steps x 2 picks, plus Astral Brilliance from `reference.include`
    assert len(main) == 5 and all(ref.potentials[k] == 6 for k in main)
    assert any(gd.item_name(p) == "Astral Brilliance" for _, p in main)
    for cid in (115, 107):
        assert len([k for k in ref.potentials if k[0] == cid]) == 2


def test_zero_value_potential_still_listed(gd, team):  # Review Focus 3
    rows = rate_potentials(gd, team, Build(), levels=[1])
    ids = {r.potential_id for r in rows}
    assert set(potential_pools(gd, 162, "main")["normal"]) <= ids
    assert set(potential_pools(gd, 107, "support")["normal"]) <= ids
    banner = [r for r in rows if r.potential_id == 510733][0]   # Banner of Glory: DEF only
    assert banner.gains == [pytest.approx(0.0, abs=1e-12)] and banner.notes


def test_gains_monotone_for_pure_stat(gd, team):
    # bar off: with breaks, a bigger stat can move a break so a weaker stretch lands in the window (real, discrete)
    from dataclasses import replace
    team = replace(team, enemy=replace(team.enemy, resilience=0))
    rows = rate_potentials(gd, team, Build(), only=[(162, 516213)])   # Veteran's Grit: flat HP
    g = rows[0].gains
    assert len(g) == 9 and all(b >= a - 1e-12 for a, b in zip(g, g[1:])) and g[0] > 0


def test_in_reference_measured_vs_removed(gd, team):
    ref = Build().with_potential(162, 516213, 6)
    row = rate_potentials(gd, team, ref, only=[(162, 516213)], levels=[6])[0]
    assert row.in_reference
    expected = gain(simulate(gd, team, Build()), simulate(gd, team, ref))
    assert row.gains[0] == pytest.approx(expected)


def test_emblem_rows_include_second_pen_line(gd, team):
    rows = rate_emblems(gd, team, Build(), members=[0])
    names = {r.line_name for r in rows}
    assert {"HP%", "Crit Rate", "Lux PEN", "Lux PEN (2nd line)", "Skill +3"} <= names
    pen1 = [r for r in rows if r.line_name == "Lux PEN"][0]
    pen2 = [r for r in rows if r.line_name == "Lux PEN (2nd line)"][0]
    assert pen1.personal > 0 and pen2.personal <= pen1.personal


def test_disc_row_carries_decode_notes(gd, team):  # Review Focus 2: undecodable/scripted parts reach the sheet
    row = rate_discs(gd, team, disc_ids=[214009, 214013])   # New Star Prelude / Voyage Blueprint: EffectType 42 shields
    assert any("shield" in n for r in row for n in r.notes)


def test_cli_rates_emblems_on_reference_build(gd, tmp_path, monkeypatch):
    import ssr.__main__ as cli
    ref = Build({(162, 516212): 6})
    seen = []
    monkeypatch.setattr(cli, "GameData", lambda _root: gd)
    monkeypatch.setattr(cli, "rate_discs", lambda *a, **k: [])
    monkeypatch.setattr(cli, "build_reference", lambda *a, **k: ref)
    monkeypatch.setattr(cli, "rate_emblems", lambda _gd, _team, build: seen.append(build) or [])
    monkeypatch.setattr(cli, "rate_potentials", lambda *a, **k: [])
    monkeypatch.setattr(cli, "write_xlsx", lambda *a, **k: None)
    cli.main([str(TEAMS / "fl_noya_skill.yaml"), "-o", str(tmp_path)])
    assert seen == [ref]
