"""Enemy resilience bar (breaks) and an exact expected-value helper for chance procs with an ICD."""
from dataclasses import dataclass, field

_EPS = 1e-9


@dataclass
class ResilienceBar:
    """The enemy's resilience bar. Hits lower it; at 0 the enemy is broken for `break_time` seconds and
    takes x`break_ratio` damage. Then the bar is full again, and after `lock_delay` more seconds it is
    locked (can't be lowered) for `lock_time` seconds. Damage while broken or locked is ignored, and a
    hit bigger than what's left breaks the bar once (the excess is discarded)."""
    max: float
    break_time: float = 10.0
    break_ratio: float = 1.5
    lock_delay: float = 0.0
    lock_time: float = 0.0
    breaks: list = field(default_factory=list)
    value: float = None

    def __post_init__(self):
        if self.value is None:
            self.value = float(self.max)

    def _end(self) -> float:
        return self.breaks[-1] + self.break_time

    def broken(self, t: float) -> bool:
        return bool(self.breaks) and self.breaks[-1] <= t < self._end() - _EPS

    def locked(self, t: float) -> bool:
        if not self.breaks or self.lock_time <= 0:
            return False
        start = self._end() + self.lock_delay
        return start - _EPS <= t < start + self.lock_time - _EPS

    def ratio(self, t: float) -> float:
        return self.break_ratio if self.broken(t) else 1.0

    def damage(self, t: float, amount: float) -> bool:
        """Lower the bar by `amount` at time `t`. True if this call broke it."""
        if amount <= 0 or self.broken(t) or self.locked(t):
            return False
        if self.breaks and self.value <= 0:
            self.value = float(self.max)   # refilled after the last break
        self.value -= amount
        if self.value <= self.max * _EPS:
            self.value = 0.0
            self.breaks.append(float(t))
            return True
        return False

    def reduce_fraction(self, t: float, frac: float) -> bool:
        """Remove `frac` of the max bar; same rules as `damage`."""
        return self.damage(t, frac * self.max)

    def broken_time(self, until: float) -> float:
        """Seconds spent broken within [0, until]."""
        return sum(max(0.0, min(s + self.break_time, until) - s) for s in self.breaks)


@dataclass
class ExpectedICD:
    """Expected proc mass of a "`chance` per trigger, at most once per `icd`" effect. Exact, because
    procs within one ICD window are mutually exclusive: the chance a trigger can proc is 1 minus the
    mass already spent in the window."""
    chance: float
    icd: float
    recent: list = field(default_factory=list)

    def fire(self, t: float) -> float:
        self.recent = [(x, m) for x, m in self.recent if t - x < self.icd - _EPS]
        p = self.chance * (1 - sum(m for _, m in self.recent))
        if p > 0:
            self.recent.append((t, p))
        return max(p, 0.0)
