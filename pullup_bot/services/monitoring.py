"""In-memory counters for daily health summary."""
from collections import defaultdict

_counters: dict = defaultdict(int)


def inc(key: str, amount: int = 1) -> None:
    """Increment the named counter by amount (default 1)."""
    _counters[key] += amount


def get(key: str) -> int:
    """Return the current value of the named counter (0 if never incremented)."""
    return _counters[key]


def reset() -> dict:
    """Return a snapshot and reset all counters."""
    snapshot = dict(_counters)
    _counters.clear()
    return snapshot
