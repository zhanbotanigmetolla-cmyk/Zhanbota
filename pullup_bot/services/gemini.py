"""
Triple-tier Gemini API key rotation.

Tier 1 (Priority):   gemini-3-flash-preview  — rotates through all keys
Tier 2 (Fallback):   gemini-2.5-flash        — if all keys hit daily limit on Tier 1
Tier 3 (Emergency):  gemini-2.5-flash-lite   — if Tier 2 also exhausted
"""

from datetime import date
from google import genai
from google.genai import types as genai_types

from ..config import GEMINI_KEYS, logger

TIERS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

RATE_LIMIT_DAILY  = "__LIMIT_DAILY__"
RATE_LIMIT_MINUTE = "__LIMIT_MINUTE__"


class APIKeyManager:
    def __init__(self, keys: list):
        self._keys = keys if keys else [GEMINI_KEYS[0] if GEMINI_KEYS else ""]
        self._clients = [genai.Client(api_key=k) for k in self._keys]
        self._exhausted: set = set()  # (key_idx, tier_idx) pairs that hit daily limit
        self._daily_count = 0
        self._count_date = date.today()
        self._all_exhausted = False

    def _reset_if_new_day(self):
        today = date.today()
        if today != self._count_date:
            self._exhausted.clear()
            self._daily_count = 0
            self._count_date = today
            self._all_exhausted = False

    def daily_count(self) -> int:
        self._reset_if_new_day()
        return self._daily_count

    def is_daily_exhausted(self) -> bool:
        self._reset_if_new_day()
        return self._all_exhausted

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
                        continue  # try next key in same tier
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
