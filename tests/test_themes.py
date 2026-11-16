from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from ssr import themes
from ssr.compare import COLOUR_RANK, EmblemResult
from ssr.emblems import emblem_options
from ssr.guide import OptimizeResult
from ssr.team import Build, load_team, team_from_doc
from ssr.themes import THEMES, ThemeRow, eligible, run_themes, themed_team

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it
NLG = TEAMS / "nazuna_leafia_gerie.yaml"


@pytest.fixture(scope="module")
def nlg(gd):
    return load_team(gd, NLG)


def test_theme_order():
    assert list(THEMES) == ["Control", "Mark", "Auto", "Skill", "Ultimate", "Crit"]
    assert THEMES["Crit"] == ("Crit Rate", "Crit DMG")


def test_eligible_nazuna_leafia_gerie(gd, nlg):
    e = eligible(gd, nlg)
    assert e["Control"] == []
    assert e["Mark"] == [2]
    assert e["Ultimate"] == [0, 1, 2]
    assert e["Skill"] == [0, 2]
    assert e["Crit"] == [0, 1, 2]


def test_eligible_skips_flora(gd):
    e = eligible(gd, load_team(gd, TEAMS / "amber_laru_flora.yaml"))
    assert 2 not in e["Mark"] and 2 not in e["Auto"]
    assert 2 in e["Skill"]


def _top(gd, cid, name, colour):
    o = next(o for o in emblem_options(gd, cid) if o.name == name)
    return [t for t in o.tiers if COLOUR_RANK[t.colour] <= COLOUR_RANK[colour]][-1].line


@pytest.mark.parametrize("tier", ["purple", "green"])
def test_forced_lines_every_slot(gd, nlg, tier):
    t = themed_team(gd, nlg, ("Crit Rate", "Crit DMG"), [0], tier)
    cid = t.members[0].char_id
    want = [_top(gd, cid, "Crit Rate", tier), _top(gd, cid, "Crit DMG", tier)]
    assert len(t.members[0].emblems) == 6
    assert sorted(map(repr, t.members[0].emblems)) == sorted(map(repr, want * 3))
    assert t.members[1].emblems == [] and t.members[2].emblems == []


def test_control_ignores_file_emblems(gd, nlg):
    line = _top(gd, nlg.members[0].char_id, "ATK%", "purple")
    t = replace(nlg, members=[replace(nlg.members[0], emblems=[line])] + list(nlg.members[1:]))
    out = themed_team(gd, t, (), [], "purple")
    assert all(m.emblems == [] for m in out.members)


@pytest.fixture
def stubs(monkeypatch):
    calls = {"optimize": [], "pinks": 0}

    def optimize(gd, team, split, **kw):
        calls["optimize"].append(team)
        if calls.get("raise_on") and calls["raise_on"](team):
            raise ValueError("boom")
        return OptimizeResult(Build(), 1.0, 1.0, "stub")

    def search_pinks(gd, team, members, **kw):
        calls["pinks"] += 1
        return team, {}
    monkeypatch.setattr(themes, "optimize", optimize)
    monkeypatch.setattr(themes, "search_pinks", search_pinks)
    monkeypatch.setattr(themes, "greedy_emblems", lambda gd, team, build, tier, **kw: EmblemResult(team.name, 2.0))
    return calls


def _doc():
    return yaml.safe_load(NLG.read_text())


def test_skipped_theme_runs_nothing(gd, nlg, stubs, monkeypatch):
    monkeypatch.setattr(themes, "eligible", lambda gd, team: {k: [] for k in THEMES})
    rows = run_themes(gd, nlg, _doc())
    assert [r.theme for r in rows] == list(THEMES)
    assert all(r.skipped for r in rows[1:]) and not rows[0].skipped
    assert len(stubs["optimize"]) == 1
    assert rows[0].total == 2.0


def test_keep_pinks_keeps_file_pinks(gd, nlg, stubs, monkeypatch):
    monkeypatch.setattr(themes, "eligible", lambda gd, team: {k: ([] if k == "Control" else [0]) for k in THEMES})
    rows = run_themes(gd, nlg, _doc(), keep_pinks=True)
    assert stubs["pinks"] == 0
    want = [[gd.item_name(p) for p in m.pinks] for m in nlg.members]
    assert all(r.pinks == want for r in rows)


def test_theme_error_is_listed(gd, nlg, stubs, monkeypatch):
    monkeypatch.setattr(themes, "eligible",
                        lambda gd, team: {k: ([] if k == "Control" else [2] if k == "Mark" else [0]) for k in THEMES})
    stubs["raise_on"] = lambda team: bool(team.members[2].emblems)
    rows = {r.theme: r for r in run_themes(gd, nlg, _doc())}
    assert "ValueError" in rows["Mark"].error
    assert all(r.total == 2.0 and r.error is None for k, r in rows.items() if k != "Mark")


def _rows():
    names = ["Nazuna", "Leafia", "Gerie"]
    return [ThemeRow("Control", [], names, total=100.0), ThemeRow("Mark", [2], names, total=120.0),
            ThemeRow("Auto", [], names, skipped=True), ThemeRow("Skill", [0, 2], names, error="ValueError: x")]


def test_page_lists_every_theme():
    from ssr.themes_page import render_html
    html = render_html(_rows(), "Emblem themes: test", ["settings"])
    for k in ("Control", "Mark", "Auto", "Skill"):
        assert k in html
    assert "120.00%" in html and "skipped" in html and "ValueError: x" in html


def test_format_rows():
    lines = themes.format_rows(_rows())
    mark = next(l for l in lines if "Mark" in l)
    assert "+20.00%" in mark
