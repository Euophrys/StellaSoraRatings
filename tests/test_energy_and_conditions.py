"""Energy granted by procs, `while:not:`, and the spec gaps they closed."""
from dataclasses import replace

import pytest
import yaml

from ssr.kit import HitSpec, resolve_potential, role_status
from ssr.sim import simulate
from ssr.team import Build, SPECS, TeamDocError, load_team, team_from_doc
from pathlib import Path

TEAMS = Path(__file__).parent / "fixtures"   # frozen copies of team files: never load teams/, the build page saves over it

TILIA, NOYA, FL_NOYA, AMBER, ANN = 107, 112, 162, 103, 123
KNIGHTS_SEAL, WINDFURY, GUIDING_STAR = 510727, 511203, 516243
BLAZING_WALTZ, DOWNWIND_JOURNEY = 510312, 512324


def _with_main_procs(team, procs):
    m = team.members[0]
    return replace(team, members=[replace(m, kit=replace(m.kit, procs=[*m.kit.procs, *procs]))] + team.members[1:])


def _amber(gd):
    return load_team(gd, TEAMS / "amber_flora_chixia.yaml")


# ---- proc energy


def test_proc_energy_brings_ults_forward(gd):
    t = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml")
    base = simulate(gd, t, Build())
    fed = simulate(gd, _with_main_procs(t, [HitSpec(hit_id=0, event="hit:self:any", energy=5.0)]), Build())
    assert fed.casts[(0, "ult")] > base.casts[(0, "ult")]


def test_proc_energy_goes_only_to_its_owner(gd):
    t = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml")
    base = simulate(gd, t, Build())
    # Firefly's own proc feeds Firefly: the main's ults don't move
    sup = t.members[1]
    fed_team = replace(t, members=[t.members[0],
                                   replace(sup, kit=replace(sup.kit, procs=[HitSpec(hit_id=0, event="hit:main:any", energy=5.0)])),
                                   t.members[2]])
    fed = simulate(gd, fed_team, Build())
    assert fed.casts[(1, "ult")] > base.casts[(1, "ult")]
    assert fed.casts[(2, "ult")] == base.casts[(2, "ult")]


def test_chance_proc_energy_is_the_expected_value(gd):
    t = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml")
    half = simulate(gd, _with_main_procs(t, [HitSpec(hit_id=0, event="hit:self:any", chance=0.5, energy=2.0)]), Build())
    sure = simulate(gd, _with_main_procs(t, [HitSpec(hit_id=0, event="hit:self:any", energy=1.0)]), Build())
    assert half.total == pytest.approx(sure.total)


def test_energy_potentials_read_their_values_from_data(gd):
    tilia = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml").members[2].kit
    assert resolve_potential(gd, tilia, KNIGHTS_SEAL, 6).procs[0].energy == pytest.approx(5.0)
    noya = load_team(gd, TEAMS / "noya_ann_canace.yaml").members[0].kit
    assert next(p for p in resolve_potential(gd, noya, WINDFURY, 1).procs if p.energy).energy == pytest.approx(1.93)
    fl = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml").members[0].kit
    assert resolve_potential(gd, fl, GUIDING_STAR, 6).procs[0].energy == pytest.approx(2.5)


def test_knights_seal_gives_tilia_more_ults(gd):
    t = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml")
    base = simulate(gd, t, Build())
    seal = simulate(gd, t, Build().with_potential(TILIA, KNIGHTS_SEAL, 6))
    assert seal.casts[(2, "ult")] > base.casts[(2, "ult")]


def test_guiding_star_gives_noya_more_ults(gd):
    t = load_team(gd, TEAMS / "fl_noya_t0_firefly_tilia.yaml")
    base = simulate(gd, t, Build())
    star = simulate(gd, t, Build().with_potential(FL_NOYA, GUIDING_STAR, 6))
    assert star.casts[(0, "ult")] > base.casts[(0, "ult")]


# ---- while:not / Blazing Waltz


def test_blazing_waltz_is_on_except_during_the_ult(gd):
    t = _amber(gd)
    base = simulate(gd, t, Build())
    waltz = simulate(gd, t, Build().with_potential(AMBER, BLAZING_WALTZ, 6))
    assert waltz.casts == base.casts
    # the ult's hit lands inside its own lock: no ATK. Everything else has it.
    assert waltz.by_slot[(0, "ult")] == pytest.approx(base.by_slot[(0, "ult")])
    assert waltz.by_slot[(0, "auto")] > base.by_slot[(0, "auto")] * 1.05


def test_blazing_waltz_is_not_an_assumed_uptime(gd):
    rp = resolve_potential(gd, _amber(gd).members[0].kit, BLAZING_WALTZ, 6)
    assert rp.modifiers[0].trigger.event == "while:not:in_action:0:ult"
    assert not rp.modifiers[0].assumed


# ---- Downwind Journey


def test_downwind_journey_boosts_nanohas_autos_shurikens_and_clones(gd):
    t = load_team(gd, TEAMS / "nanoha_ann_canace.yaml")
    base = simulate(gd, t, Build())
    dj = simulate(gd, t, Build().with_potential(ANN, DOWNWIND_JOURNEY, 1))
    assert dj.by_slot[(0, "auto")] > base.by_slot[(0, "auto")] * 1.02
    assert dj.by_slot[(0, "skill")] > base.by_slot[(0, "skill")] * 1.02
    assert dj.by_slot[(0, "ult")] > base.by_slot[(0, "ult")] * 1.02                # the clones use her attacks
    assert dj.by_slot[(1, "skill")] == pytest.approx(base.by_slot[(1, "skill")])   # Ann's own hits


def test_projectile_tag_does_not_widen_any_nanoha_potential(gd):
    """`projectile` is on all her attacks: in a potential's scope it would reach far more than that potential says."""
    kit = load_team(gd, TEAMS / "nanoha_ann_canace.yaml").members[0].kit
    for p in kit.potentials:
        for m in resolve_potential(gd, kit, p, 6).modifiers:
            assert "projectile" not in m.hit_tags, p


def test_downwind_journey_does_nothing_for_a_melee_main(gd):
    t = load_team(gd, TEAMS / "noya_ann_canace.yaml")
    base = simulate(gd, t, Build())
    assert simulate(gd, t, Build().with_potential(ANN, DOWNWIND_JOURNEY, 1)).total == pytest.approx(base.total)


# ---- Amber's first key talent


def test_a_dance_with_bullets_stacks_skill_dmg(gd):
    doc = yaml.safe_load((TEAMS / "amber_flora_chixia.yaml").read_text(encoding="utf-8"))
    doc["members"][0]["talents"] = 1
    t = team_from_doc(gd, doc, "amber_flora_chixia")
    assert t.members[0].talents == 1
    on = simulate(gd, t, Build())
    assert not any("key talent" in u and "Amber" in u for u in on.unknown_modifiers)
    m = t.members[0]
    off = simulate(gd, replace(t, members=[replace(m, kit=replace(m.kit, talents={}))] + t.members[1:]), Build())
    assert off.by_slot[(0, "skill")] < on.by_slot[(0, "skill")] <= off.by_slot[(0, "skill")] * 1.16   # 10 x 1.6%
    assert on.by_slot[(0, "auto")] == pytest.approx(off.by_slot[(0, "auto")])


# ---- stub roles


@pytest.mark.parametrize("cid,role,want", [
    (FL_NOYA, "main", "ok"), (TILIA, "support", "ok"),
    (TILIA, "main", "frames"), (AMBER, "support", "frames"), (FL_NOYA, "support", "frames"),
    (116, "main", "frames"), (155, "main", "frames"),
])
def test_role_status(cid, role, want):
    assert role_status(SPECS / f"{cid}.yaml", role) == want


@pytest.mark.parametrize("sec,want", [("stub: true", "stub"), ("untimed: true", "untimed"), ("timing: frames", "frames"),
                                     ("actions: {}", "ok")])
def test_role_status_flags(tmp_path, sec, want):
    p = tmp_path / "1.yaml"
    p.write_text(f"char_id: 1\nmain:\n  {sec}\n", encoding="utf-8")
    assert role_status(p, "main") == want
    assert role_status(p, "support") == "missing"


def test_a_missing_role_is_a_readable_team_error(gd, tmp_path):
    (tmp_path / "116.yaml").write_text("char_id: 116\nsupport:\n  actions: {}\n", encoding="utf-8")
    doc = {"members": [{"trekker": "Ridge", "role": "main"}]}
    with pytest.raises(TeamDocError, match="Ridge: no main kit"):
        team_from_doc(gd, doc, specs=tmp_path)
