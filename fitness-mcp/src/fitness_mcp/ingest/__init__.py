"""Pluggable ingest adapters.

Phase 1 — pullup_bot        : implemented
Phase 2 — xiaomi_export     : not started
Phase 3 — mifitness_cloud   : not started, optional, fragile by nature
Skipped — strava            : stub only, see strava.py for why
"""

from .base import Adapter, IngestResult, run_adapter

__all__ = ["Adapter", "IngestResult", "run_adapter"]
