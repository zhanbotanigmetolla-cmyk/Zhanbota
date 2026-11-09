"""Strava adapter — DELIBERATELY NOT IMPLEMENTED.

As of 2026-06-30, Standard-tier Strava API access requires an active paid
Strava subscription. Self-hosting does not route around it: the gate is on the
API credentials, not on where the client runs.

This file exists so the shape is already decided if a subscription is ever
bought. It intentionally contains no request code, no endpoint URLs and no
OAuth flow. Do not "helpfully" fill this in without the subscription — it will
fail at the authorization step, not at the code.

To implement later:
  * register an application, obtain client id/secret
  * OAuth 2 authorization-code flow, scope ``activity:read_all``
  * paginate ``/athlete/activities``, map each activity onto WorkoutRow with
    ``source="strava"`` and ``source_id=str(activity["id"])``
  * rate limits apply per 15 minutes and per day; back off rather than retry hard
"""

from __future__ import annotations

from typing import Iterable

from ..db import WorkoutRow

name = "strava"


class StravaAdapter:
    """Placeholder conforming to the Adapter protocol. Always refuses to run."""

    name = "strava"

    def fetch(self) -> Iterable[WorkoutRow]:
        raise NotImplementedError(
            "The Strava adapter is not built. Standard-tier API access requires a "
            "paid Strava subscription (policy change effective 2026-06-30). "
            "See the module docstring for what to implement if that changes."
        )
