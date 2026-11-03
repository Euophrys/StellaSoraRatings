from ssr.resilience import ResilienceBar, ExpectedICD
import pytest


def _bar(**kw):
    return ResilienceBar(**{**dict(max=100, break_time=10, break_ratio=1.5, lock_delay=0, lock_time=0), **kw})


def test_break_and_window():
    b = _bar()
    assert b.damage(1, 60) is False
    assert b.damage(2, 50) is True
    assert b.breaks == [2.0]
    assert b.broken(2.0) and b.broken(11.99) and not b.broken(12.0)
    assert b.ratio(5) == 1.5 and b.ratio(1) == 1.0
    assert b.damage(5, 1000) is False and b.breaks == [2.0]   # ignored while broken


def test_overkill_breaks_once():
    b = _bar()
    assert b.damage(0, 1000) is True and b.breaks == [0.0]
    assert b.damage(10.0, 99) is False   # refilled to full; excess wasn't carried over


def test_refill_boundary():
    b = _bar(); b.damage(2, 100)
    assert b.damage(12.0, 99) is False and b.damage(13, 1) is True
    assert b.breaks == [2.0, 13.0]


def test_lock_window():   # break at 0, refill at 10, lock 11.3..16.0
    b = _bar(lock_delay=1.3, lock_time=4.7); b.damage(0, 100)
    assert b.damage(11.0, 50) is False      # applies (before the lock)
    assert b.damage(11.3, 50) is False      # locked: ignored
    assert b.damage(16.0, 50) is True


def test_reduce_fraction():
    b = _bar(max=250e6)
    assert b.reduce_fraction(0, 0.004) is False
    assert b.damage(0.1, 250e6 - 1e6) is True


def test_broken_time():
    b = _bar(); b.damage(2, 100)
    assert b.broken_time(15) == pytest.approx(10)
    b2 = _bar(); b2.damage(10, 100)
    assert b2.broken_time(15) == pytest.approx(5)


def test_expected_icd_certain():
    e = ExpectedICD(1.0, 0.5)
    assert [e.fire(0), e.fire(0.3), e.fire(0.5)] == [1.0, 0.0, 1.0]


def test_expected_icd_form_breaker_claws():   # Cosette's 13 claws (specs/trekkers/142.yaml offsets)
    offs = [0.967, 1.3, 1.633, 1.967, 2.433, 2.8, 3.133, 3.467, 3.933, 4.3, 4.633, 4.967, 5.433]
    e = ExpectedICD(0.3, 0.5)
    assert sum(e.fire(t) for t in offs) == pytest.approx(3.0533, abs=1e-3)
