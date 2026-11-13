from pathlib import Path

import yaml

from ssr.finder import team_docs
from ssr.team import team_from_doc

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
