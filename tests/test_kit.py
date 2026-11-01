import pytest
from ssr.kit import load_kit, pink_ids, resolve_potential, SPECS
from ssr.game import potential_pools
from ssr.stats import SKILL_CRIT_RATE

CASES = [(162, "main"), (115, "support"), (107, "support")]


def _all_hitspecs(k):
    for a in k.actions.values():
        yield from a.hits
    for p in k.potentials.values():
        for hs in list(p.add_hits.values()) + list(p.replace_hits.values()):
            yield from hs
        for a in p.add_actions.values():
            yield from a.hits
        for pr in p.procs:
            yield pr


def test_specs_load(gd):
    for cid, role in CASES:
        k = load_kit(gd, SPECS / f"{cid}.yaml", role)
        assert set(k.actions) >= {"skill", "ult"}
        if role == "support":
            assert "auto" not in k.actions


def test_spec_hits_exist(gd):
    for cid, role in CASES:
        k = load_kit(gd, SPECS / f"{cid}.yaml", role)
        for hs in _all_hitspecs(k):
            assert str(hs.hit_id) in gd.table("HitDamage"), hs.hit_id
            assert str(hs.hit_id).startswith(str(cid)), hs.hit_id


def test_spec_potentials_belong_to_pools(gd):
    for cid, role in CASES:
        k = load_kit(gd, SPECS / f"{cid}.yaml", role)
        pools = potential_pools(gd, cid, role)
        allowed = set(pools["pink"]) | set(pools["normal"]) | set(pools["common"])
        assert set(k.potentials) <= allowed, set(k.potentials) - allowed


def test_pinks_resolved(gd):
    assert {gd.item_name(i) for i in pink_ids(gd, 162, ["Lucent Blitz", "Dawnflare"])} == {"Lucent Blitz", "Dawnflare"}


def test_noya_timings(gd):
    k = load_kit(gd, SPECS / "162.yaml", "main")
    assert k.actions["skill"].lock == 5.0 and k.actions["ult"].lock == 4.0


def test_resolve_potential_scopes_override(gd):
    k = load_kit(gd, SPECS / "162.yaml", "main")
    rp = resolve_potential(gd, k, 516205, 6)
    crit = [m for m in rp.modifiers if m.stat == SKILL_CRIT_RATE]
    assert crit and {"longsword", "glow"} <= set(crit[0].hit_tags) and not crit[0].needs_scope
    assert any(h.hit_id == 162310006 for h in rp.add_hits["skill"])


def test_ref_values_resolve_at_level(gd):
    k = load_kit(gd, SPECS / "107.yaml", "support")
    rp1, rp6 = resolve_potential(gd, k, 510722, 1), resolve_potential(gd, k, 510722, 6)
    assert rp1.cd_reduce and rp1.cd_reduce["seconds"] > 0


def test_base_rules_reset_cd(gd):
    k = load_kit(gd, SPECS / "115.yaml", "support")
    assert k.reset_cd == {"ult": "skill"}


def test_every_pool_potential_resolves(gd):
    from ssr.kit import resolve_buffs
    for cid, role in CASES:
        k = load_kit(gd, SPECS / f"{cid}.yaml", role)
        pools = potential_pools(gd, cid, role)
        for pid in pools["pink"] + pools["normal"] + pools["common"]:
            for lv in (1, 6, 9):
                resolve_potential(gd, k, pid, lv)
        resolve_buffs(gd, k, {"auto": 10, "skill": 10, "ult": 10})


def test_noya_starender_buff(gd):
    from ssr.kit import resolve_buffs
    from ssr.stats import CRIT_RATE
    k = load_kit(gd, SPECS / "162.yaml", "main")
    b = resolve_buffs(gd, k, {"ult": 10})
    assert b[0].stat == CRIT_RATE and b[0].value == pytest.approx(0.2) and b[0].trigger.duration == 30
