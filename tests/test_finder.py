from collections import Counter
from dataclasses import replace
from pathlib import Path

import yaml

import pytest

from ssr import finder
from ssr.finder import coarse_build, find_teams, team_docs
from ssr.sim import simulate
from ssr.team import Build, load_team, team_from_doc
from ssr.web.jobs import JobCancelled

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it
TEMPLATE = yaml.safe_load((TEAMS / "nazuna_leafia_gerie.yaml").read_text())
TERRA = {"Ridge", "Sparkla", "Gerie", "Nazuna", "Springseek Coronis", "Leafia"}


def test_main_gets_every_support_pair(gd):
    docs = team_docs(gd, TEMPLATE, "Nazuna", "main")
    assert len(docs) == 10
    assert all(d["members"][0]["trekker"] == "Nazuna" and d["members"][0]["role"] == "main" for d in docs)
    assert all([m["role"] for m in d["members"][1:]] == ["support", "support"] for d in docs)
    assert {m["trekker"] for d in docs for m in d["members"]} == TERRA
    assert len({frozenset(m["trekker"] for m in d["members"][1:]) for d in docs}) == 10
    assert docs[0]["name"] == "nazuna_ridge_sparkla"


def test_support_varies_the_main(gd):
    docs = team_docs(gd, TEMPLATE, "Nazuna", "support")
    assert len(docs) == 20
    assert all(sum(m["trekker"] == "Nazuna" for m in d["members"]) == 1 for d in docs)
    assert all(d["members"][0]["trekker"] != "Nazuna" for d in docs)
    assert len({(d["members"][0]["trekker"], frozenset(m["trekker"] for m in d["members"][1:])) for d in docs}) == 20


def test_any_is_the_union(gd):
    assert len(team_docs(gd, TEMPLATE, "Nazuna", "any")) == 30


def test_exclude(gd):
    docs = team_docs(gd, TEMPLATE, "Nazuna", "main", exclude=["Ridge"])
    assert len(docs) == 6 and all("Ridge" not in {m["trekker"] for m in d["members"]} for d in docs)


def test_bad_role_or_trekker(gd):
    import pytest
    with pytest.raises(ValueError):
        team_docs(gd, TEMPLATE, "Nazuna", "dps")
    with pytest.raises(ValueError):
        team_docs(gd, TEMPLATE, "Nobody", "main")


def test_template_settings_kept_and_member_bits_dropped(gd):
    tpl = {**TEMPLATE, "hold": [{"member": 2, "action": "ult", "until": 5}],
           "reference": {"steps": 1, "include": ["Touch of Nature", "Not A Potential"]}}
    for d in team_docs(gd, tpl, "Nazuna", "main"):
        assert "hold" not in d and d["discs"] == TEMPLATE["discs"] and d["enemy"] == TEMPLATE["enemy"]
        assert d["reference"] == {"steps": 1, "include": ["Touch of Nature"]}   # Nazuna main has it
        team_from_doc(gd, d)   # every generated doc loads
    assert tpl["hold"]   # template not mutated


def small_team(gd):
    team = load_team(gd, TEAMS / "nazuna_leafia_gerie.yaml")
    return replace(team, fight_length=20, reference={"steps": 0})


def test_coarse_build_picks_and_level(gd):
    team = small_team(gd)
    build, total = coarse_build(gd, team, picks=(2, 1, 0))
    per = Counter(cid for cid, _p in build.potentials)
    assert per[156] == 2 and per[161] == 1 and per[149] == 0
    assert set(build.potentials.values()) == {6}
    assert total == simulate(gd, team, build).total > simulate(gd, team, Build()).total


def test_coarse_build_level_param(gd):
    build, _ = coarse_build(gd, small_team(gd), picks=(1, 0, 0), level=3)
    assert list(build.potentials.values()) == [3]


FAST = {**TEMPLATE, "fight_length": 20, "reference": {"steps": 0}, "budget": [2, 1, 1], "budget_total": None}


def test_find_teams_ranks_and_finalists(gd):
    rows = find_teams(gd, FAST, "Nazuna", "main", top=2, emblems="none", picks=(1, 1, 0),
                      exclude=["Ridge", "Sparkla"])          # 3 teams
    assert len(rows) == 3 and [r.finalist for r in rows] == [True, True, False]
    assert rows[0].total >= rows[1].total and all(r.error is None for r in rows)
    assert min(r.screen_total for r in rows[:2]) >= rows[2].screen_total
    assert all(len(p) == 2 for r in rows for p in r.pinks)
    assert all(r.members[0] == "Nazuna" and r.method for r in rows[:2])
    for r in rows:
        t = team_from_doc(gd, r.doc)
        assert [len(m.pinks) for m in t.members] == [2, 2, 2]
    assert [sum(m["targets"].values()) for m in rows[0].doc["members"]] == [2, 1, 1]


def test_finalist_emblems_round_trip(gd):
    rows = find_teams(gd, FAST, "Nazuna", "main", top=1, emblems="green", picks=(1, 0, 0),
                      exclude=["Ridge", "Sparkla", "Springseek Coronis"])   # 1 team
    t = team_from_doc(gd, rows[0].doc)
    assert any(m.emblem_slots and any(m.emblem_slots) for m in t.members)


def test_failing_team_is_reported(gd, monkeypatch):
    real = finder.coarse_build

    def boom(gd_, team, *a, **k):
        if any(m.char_id == 161 for m in team.members):
            raise RuntimeError("kaput")
        return real(gd_, team, *a, **k)
    monkeypatch.setattr(finder, "coarse_build", boom)
    rows = find_teams(gd, FAST, "Nazuna", "main", top=1, emblems="none", picks=(1, 0, 0),
                      exclude=["Ridge", "Sparkla"])
    assert rows[-1].error == "RuntimeError: kaput" and rows[0].error is None and rows[0].finalist
    assert sum(r.error is not None for r in rows) == 2   # both Leafia teams


def test_cancel_is_not_swallowed(gd):
    def progress(phase, done, total):
        if done >= 1:
            raise JobCancelled()
    with pytest.raises(JobCancelled):
        find_teams(gd, FAST, "Nazuna", "main", top=1, emblems="none", picks=(1, 0, 0),
                   exclude=["Ridge", "Sparkla"], progress=progress)


def test_names_ignore_case(gd):
    docs = team_docs(gd, TEMPLATE, "nazuna", "main", exclude=["ridge", "SPARKLA"])
    assert len(docs) == 3 and all(d["members"][0]["trekker"] == "Nazuna" for d in docs)
    assert {m["trekker"] for d in docs for m in d["members"]} == {"Nazuna", "Gerie", "Springseek Coronis", "Leafia"}


def test_cli_writes_a_page(gd, tmp_path, capsys):
    tpl = tmp_path / "tpl.yaml"
    tpl.write_text(yaml.safe_dump(FAST))
    out, page = tmp_path / "out.yaml", tmp_path / "finder.html"
    finder.main(["nazuna", "--template", str(tpl), "--role", "Main", "--top", "1", "--emblems", "None",
                 "--picks", "1,0,0", "--exclude", "ridge", "sparkla", "springseek coronis", "-o", str(out),
                 "--html", str(page), "--no-open"])
    html = page.read_text()
    assert html.startswith("<!doctype html>") and "<title>" in html
    assert "excluded Ridge, Sparkla, Springseek Coronis" in html
    assert "Nazuna" in html and "Gerie" in html and "100.00%" in html and "Optimized" in html and "Screened" in html
    assert str(page) in capsys.readouterr().out
    docs = yaml.safe_load(out.read_text())
    assert len(docs) == 1 and team_from_doc(gd, docs[0]).members[0].pinks


def test_page_escapes_and_lists_errors():
    rows = [finder.FinderRow(["A", "B", "C"], [["p", "q"], ["r", "s"], ["t", "u"]], 10.0, 20.0, True, "greedy",
                             {"members": [{"trekker": "A", "targets": {"X": 6}, "emblems": []}] * 3}),
            finder.FinderRow(["A", "<b>", "C"], [[], [], []], None, error="RuntimeError: <kaput>")]
    html = finder.render_html(rows, title="T", settings=["s"])
    assert "&lt;kaput&gt;" in html and "<kaput>" not in html and "&lt;b&gt;" in html
    assert "X Lv6" in html   # finalist build listed
