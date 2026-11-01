from ssr.builds import pink_pairs, with_pinks


def test_six_pairs_per_member(gd, team):
    for i in range(3):
        pairs = pink_pairs(gd, team, i)
        assert len(pairs) == 6 and len(set(pairs)) == 6


def test_with_pinks_leaves_original(gd, team):
    t = with_pinks(team, 0, [516203, 516204])
    assert t.members[0].pinks == [516203, 516204]
    assert team.members[0].pinks == [516201, 516202]
    assert t.members[1] is team.members[1]
