import pytest


def test_char_names(gd):
    assert gd.char_name(162) == "Firstlight Noya"
    assert gd.char_name(107) == "Tilia"
    assert gd.char_name(115) == "Firefly"


def test_potential_and_disc_names(gd):
    assert gd.item_name(510301) == "Dominant Firepower"
    assert gd.find_item("Eternal Brilliance") == 214067
    assert gd.find_item("Ripples of Nostalgia") == 214038
    assert gd.find_item("My Guiding Star") == 214066


def test_find_item_missing_raises(gd):
    with pytest.raises(KeyError):
        gd.find_item("No Such Item Name Xyz")
