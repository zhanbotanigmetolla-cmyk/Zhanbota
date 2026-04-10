"""
Quad-tier Gemini API key rotation.

Real free-tier limits (20 RPD per key per model, except Tier 4):
  Tier 1: gemini-3-flash-preview   — 20 RPD × 4 keys = 80/day  (best quality)
  Tier 2: gemini-2.5-flash         — 20 RPD × 4 keys = 80/day
  Tier 3: gemini-2.5-flash-lite    — 20 RPD × 4 keys = 80/day
  Tier 4: gemini-3.1-flash-lite    — 500 RPD × 4 keys = 2000/day (emergency volume)

Total theoretical max: ~2240 requests/day across all keys and tiers.

Exhaustion state persists across bot restarts within the same calendar day
by writing to a small JSON sidecar file.
"""

import json
import os
from datetime import date
from google import genai
from google.genai import types as genai_types

from ..config import GEMINI_KEYS, logger

TIERS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
]

# Human-readable short names for admin display
TIER_LABELS = {
    "gemini-3-flash-preview": "3-Flash",
    "gemini-2.5-flash":       "2.5-Flash",
    "gemini-2.5-flash-lite":  "2.5-Lite",
    "gemini-3.1-flash-lite":  "3.1-Lite★",
}

RATE_LIMIT_DAILY  = "__LIMIT_DAILY__"
RATE_LIMIT_MINUTE = "__LIMIT_MINUTE__"

# Sidecar file: persists exhaustion state across restarts within the same day
_STATE_FILE = os.path.expanduser("~/pullup_gemini_state.json")


def _load_state() -> dict:
    try:
        with open(_STATE_FILE) as f:
            data = json.load(f)
        if data.get("date") == str(date.today()):
            return data
    except Exception as e:
        logger.debug(f"[gemini] load state: {e}")
    return {"date": str(date.today()), "exhausted": [], "daily_count": 0}


def _save_state(exhausted: set, daily_count: int):
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump({
                "date": str(date.today()),
                "exhausted": [list(e) for e in exhausted],
                "daily_count": daily_count,
            }, f)
    except Exception as e:
        logger.warning(f"[gemini] save state failed: {e}")


class APIKeyManager:
    def __init__(self, keys: list):
        self._keys = keys if keys else [GEMINI_KEYS[0] if GEMINI_KEYS else ""]
        self._clients = [genai.Client(api_key=k) for k in self._keys]

        state = _load_state()
        self._exhausted: set = {tuple(e) for e in state.get("exhausted", [])}
        self._daily_count: int = state.get("daily_count", 0)
        self._count_date = date.today()
        self._all_exhausted = self._check_all_exhausted()

    def _check_all_exhausted(self) -> bool:
        for t in range(len(TIERS)):
            for k in range(len(self._keys)):
                if (k, t) not in self._exhausted:
                    return False
        return True

    def _reset_if_new_day(self):
        today = date.today()
        if today != self._count_date:
            self._exhausted.clear()
            self._daily_count = 0
            self._count_date = today
            self._all_exhausted = False
            _save_state(self._exhausted, self._daily_count)

    def daily_count(self) -> int:
        self._reset_if_new_day()
        return self._daily_count

    def is_daily_exhausted(self) -> bool:
        self._reset_if_new_day()
        return self._all_exhausted

    def exhausted_summary(self) -> list[dict]:
        """Returns list of {tier, key, model} for all exhausted combos — for admin display."""
        return [
            {"tier": t, "key": k, "model": TIERS[t]}
            for (k, t) in sorted(self._exhausted)
            if t < len(TIERS) and k < len(self._keys)
        ]

    async def chat(self, system_prompt: str, history: list, user_msg: str) -> tuple[str, str]:
        """
        Returns (response_text, model_used).
        response_text may be RATE_LIMIT_DAILY, RATE_LIMIT_MINUTE, or "" on error.
        model_used is the model name that succeeded, or "" on failure.
        """
        self._reset_if_new_day()

        for tier_idx, model in enumerate(TIERS):
            for key_idx, client in enumerate(self._clients):
                if (key_idx, tier_idx) in self._exhausted:
                    continue
                try:
                    gemini_history = [
                        genai_types.Content(
                            role=h["role"],
                            parts=[genai_types.Part(text=h["content"])]
                        )
                        for h in history
                    ]
                    session = client.aio.chats.create(
                        model=model,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=system_prompt
                        ),
                        history=gemini_history,
                    )
                    response = await session.send_message(user_msg)
                    self._daily_count += 1
                    _save_state(self._exhausted, self._daily_count)
                    logger.info(
                        f"[Gemini] key={key_idx} tier={tier_idx} ({model}) "
                        f"ok, daily_total={self._daily_count}"
                    )
                    return response.text or "", model
                except Exception as e:
                    err = str(e).lower()
                    if "429" in err or "quota" in err or "resource_exhausted" in err or "rate" in err:
                        if "per_minute" in err or "per minute" in err or "minute" in err:
                            return RATE_LIMIT_MINUTE, ""
                        logger.warning(
                            f"[Gemini] key={key_idx} tier={tier_idx} ({model}) daily limit hit"
                        )
                        self._exhausted.add((key_idx, tier_idx))
                        _save_state(self._exhausted, self._daily_count)
                        continue  # try next key in same tier
                    if "503" in err or "unavailable" in err or "overloaded" in err:
                        logger.warning(
                            f"[Gemini] key={key_idx} tier={tier_idx} ({model}) overloaded, trying next tier"
                        )
                        break  # skip remaining keys for this tier, try next tier
                    logger.error(f"[Gemini] key={key_idx} tier={tier_idx} ({model}): {e}")
                    return "", ""

        self._all_exhausted = True
        logger.warning("[Gemini] All tiers and keys exhausted for today")
        return RATE_LIMIT_DAILY, ""


_manager: "APIKeyManager | None" = None


def get_manager() -> APIKeyManager:
    global _manager
    if _manager is None:
        _manager = APIKeyManager(GEMINI_KEYS)
    return _manager
