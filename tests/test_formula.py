import pytest
from ssr.formula import def_amend, er_amend, Enemy, hit_damage
from ssr.game import hit, char_base_stats
from ssr.stats import SKILL_DMG, elem_stat, ELEM_PEN_BASE, ELEM_TAKEN_BASE


def test_def():
    assert def_amend(500) == pytest.approx(0.5)
    assert def_amend(350) == pytest.approx(0.60227, abs=1e-5)
    assert def_amend(0) == 1.0


@pytest.mark.parametrize("res,mult", [(250, .75), (140, .9216), (30, .9964), (570, .54783), (750, .4), (2000, .01), (5000, .01)])
def test_res(res, mult):
    assert er_amend(res, 0) == pytest.approx(mult, abs=1e-4)


def test_res_negative_no_vul():  # Review Focus 4
    assert er_amend(250, 400) == 1.0


def test_res_negative_vul():
    assert er_amend(0, 60, vul=0.05) == pytest.approx(1.032)


def test_pen_raises_damage():
    assert er_amend(250, 110) == pytest.approx(0.9216, abs=1e-4)


SKILL_HIT = 162310001
AUTO_HIT = 162100001


def test_hit_damage_scales_linearly_with_skill_dmg(gd):
    me = char_base_stats(gd, 162)
    buffed = me.copy(); buffed.add_stat(SKILL_DMG, 0.10)
    e = Enemy()
    sk, au = hit(gd, SKILL_HIT), hit(gd, AUTO_HIT)
    assert sk.damage_type == 2 and au.damage_type == 1
    assert hit_damage(sk, 10, buffed, e) / hit_damage(sk, 10, me, e) == pytest.approx(1.10)
    assert hit_damage(au, 10, buffed, e) / hit_damage(au, 10, me, e) == pytest.approx(1.00)


def test_hit_damage_uses_pen_and_taken(gd):
    me = char_base_stats(gd, 162)
    h = hit(gd, AUTO_HIT)
    base = hit_damage(h, 10, me, Enemy(res=250))
    pen = me.copy(); pen.add_stat(elem_stat(ELEM_PEN_BASE, 5), 110)
    assert hit_damage(h, 10, pen, Enemy(res=250)) / base == pytest.approx(0.9216 / 0.75, abs=1e-4)
    e = Enemy(res=250); e.taken.add_stat(elem_stat(ELEM_TAKEN_BASE, 5), 0.2)
    assert hit_damage(h, 10, me, e) / base == pytest.approx(1.2)


def test_hit_damage_expected_crit(gd):
    me = char_base_stats(gd, 162)  # 5% crit, 150% crit dmg
    h = hit(gd, AUTO_HIT)
    e = Enemy(res=0, defense=0)
    expected = me.final(h.base_stat) * 1.25 * (0.95 + 0.05 * 1.5) * 1.0  # hit_pct lvl10 = 1.25
    assert hit_damage(h, 10, me, e) == pytest.approx(expected)


def test_dmg_multiplier_is_separate_from_the_buckets():
    from ssr.game import Hit
    from ssr.stats import DMG, DMG_MULT, StatBlock
    h = Hit(id=1, damage_type=2, element=5, base_stat=1, source_type=0, pct=(10000.0,))
    a = StatBlock(); a.set_base(1, 1000); a.add_stat(DMG, 0.5)
    b = a.copy(); b.add_stat(DMG_MULT, 0.36)
    assert hit_damage(h, 1, b, Enemy()) == pytest.approx(hit_damage(h, 1, a, Enemy()) * 1.36)
