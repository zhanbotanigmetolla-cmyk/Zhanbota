"""In-memory counters for daily health summary."""
from collections import defaultdict

_counters: dict = defaultdict(int)


def inc(key: str, amount: int = 1) -> None:
    _counters[key] += amount


def get(key: str) -> int:
    return _counters[key]


def reset() -> dict:
    """Return a snapshot and reset all counters."""
    snapshot = dict(_counters)
    _counters.clear()
    return snapshot
