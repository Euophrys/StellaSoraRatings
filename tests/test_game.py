import pytest
from ssr.game import (char_base_stats, skill_ids, skill_cd, ult_energy, hit, hit_pct,
                      disc_base_stats, potential_pools)
from ssr.stats import HP, ATK, CRIT_RATE, CRIT_DMG


def test_ult_energy(gd):
    for cid, e in [(162, 235), (107, 190), (115, 300)]:
        assert ult_energy(gd, skill_ids(gd, cid, "main")["ult"]) == e


def test_skill_cd(gd):
    assert skill_cd(gd, skill_ids(gd, 162, "main")["skill"]) == pytest.approx(10.0)


def test_noya_base(gd):
    s = char_base_stats(gd, 162)
    assert s.base(HP) > 0 and s.get(CRIT_RATE) == pytest.approx(0.05) and s.get(CRIT_DMG) == pytest.approx(1.5)


def test_hit(gd):
    h = hit(gd, 162100001)
    assert h.base_stat == HP and h.element == 5 and h.damage_type == 1
    assert hit_pct(h, 1) == pytest.approx(0.45) and hit_pct(h, 99) == h.pct[-1]


def test_filler_disc(gd):
    s = disc_base_stats(gd, 214067, copies=6)
    assert s.flat[ATK] == 1533 and s.flat[HP] == 6990


def test_disc_c1_has_no_extra(gd):
    assert disc_base_stats(gd, 214067, copies=1).flat[ATK] == 883


def test_pools(gd):
    assert potential_pools(gd, 103, "main")["pink"] == [510301, 510302, 510303, 510304]
    assert potential_pools(gd, 103, "support")["pink"] == [510321, 510322, 510323, 510324]


def test_disc_substat_elem_dmg(gd):
    from ssr.stats import elem_stat, ELEM_DMG_BASE, SKILL_DMG
    s = disc_base_stats(gd, 214066, copies=1)  # My Guiding Star: LEE 1500
    assert s.get(elem_stat(ELEM_DMG_BASE, 5)) == pytest.approx(0.15)
    assert disc_base_stats(gd, 214005).get(SKILL_DMG) == pytest.approx(0.24)


def test_hit_level_source(gd):
    from ssr.game import hit_level
    lv = {"auto": 7, "skill": 8, "ult": 9}
    pots = {516205: 4}
    assert hit_level(hit(gd, 162100001), lv, pots) == 7        # levelTypeData 3, slot 5 = auto
    assert hit_level(hit(gd, 162310001), lv, pots) == 8        # slot 2 = skill
    assert hit_level(hit(gd, 162400001), lv, pots) == 9        # slot 4 = ult
    assert hit_level(hit(gd, 162310006), lv, pots) == 4        # levelTypeData 1 = Prism Warp's level
    assert hit_level(hit(gd, 162310006), lv, {}) == 1
    assert hit_level(hit(gd, 162000001), lv, pots) == 9        # levelTypeData 4 = ascension, max
