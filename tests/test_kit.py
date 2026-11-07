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
            if hs.hit_id == 0:   # a marker: no damage (specs/README.md)
                continue
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
    assert k.actions["skill"].lock == 2.1 and k.actions["ult"].lock == 3.23 and k.actions["auto"].duration == 4.7   # user frame-timed


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
    b = [m for m in resolve_buffs(gd, k, {"ult": 10}) if m.stat == CRIT_RATE]
    assert b[0].value == pytest.approx(0.2) and b[0].trigger.duration == 30


def test_noya_glimmer_buffs(gd):
    from ssr.kit import resolve_buffs
    from ssr.stats import elem_stat, ELEM_TAKEN_BASE, DMG
    k = load_kit(gd, SPECS / "162.yaml", "main")
    b = resolve_buffs(gd, k, {"auto": 10, "skill": 10, "ult": 10})
    g = [m for m in b if m.name == "glimmer"][0]
    assert g.stat == elem_stat(ELEM_TAKEN_BASE, 5) and g.value == pytest.approx(0.005) and g.target == "enemy"
    assert g.trigger.event == "mark:self" and g.trigger.max_stacks == 3 and g.trigger.duration == 6
    a = [m for m in b if m.stat == DMG and "auto" in m.hit_tags][0]
    assert a.value == pytest.approx(0.12) and a.trigger.event == "while:status:glimmer" and a.trigger.per_stack


def test_buff_requires_all_gerie_lethal(gd):
    """Gerie's Lethal lasts 8.5 s, +4 s with Lingering Hunger, x1.5 cage with Piercing Sorrow; both: 16.75 s."""
    from ssr.kit import resolve_buffs
    k = load_kit(gd, SPECS / "149.yaml", "main")

    def lethal(owned):
        return sorted(m.trigger.duration for m in resolve_buffs(gd, k, {"skill": 10}, owned) if m.name == "lethal")

    assert lethal(set()) == [8.5]
    assert lethal({514907}) == [12.5]
    assert lethal({514910}) == [12.75]
    assert lethal({514907, 514910}) == [16.75]
