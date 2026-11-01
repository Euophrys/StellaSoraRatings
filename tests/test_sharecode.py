import pytest

from ssr.sharecode import SharePreset, decode_share, encode_share

CODE = "AAAAZwAAAH4AAACNobDDAY6gNhhhiKGGw2wA"   # user's Amber / Flora / Chixia preset (preset.png)


def test_decode_users_code(gd):
    p = decode_share(gd, CODE)
    assert p.char_ids == [103, 126, 141]
    names = {gd.item_name(k): v for k, v in p.levels[0].items()}
    assert names == {"Ardent Trigger": 6, "Confident Mode": 6, "Grand Finale": 6, "Keen Accent": 6,
                     "Bursting Spark": 6, "Soul-Hunting Spark": 6, "Overloaded Spark": 1}
    assert {gd.item_name(x) for x in p.pinks[0]} == {"Dominant Firepower", "Precise Temperature Control"}
    assert all(len(x) == 2 for x in p.pinks)


def test_round_trip_all_builtin_presets(gd):
    rows = list(gd.table("PotentialPreset").values())
    assert len(rows) >= 80
    for r in rows:
        assert encode_share(gd, decode_share(gd, r["ShareCode"])) == r["ShareCode"]


def test_encode_clamps_levels(gd):
    p = decode_share(gd, CODE)
    pid = next(iter(p.levels[0]))
    p.levels[0][pid] = 9
    again = decode_share(gd, encode_share(gd, p))
    assert again.levels[0][pid] == 6


@pytest.mark.parametrize("code", ["hello", "", "AAAA", "AAAAZwAAAH4AAACNobDDAY6gNhhhiKGGw2wAAAAA",
                                  "AAAAAQAAAH4AAACNobDDAY6gNhhhiKGGw2wA"])
def test_garbage_code_is_value_error(gd, code):
    with pytest.raises(ValueError, match="not a Stella Sora preset code"):
        decode_share(gd, code)
