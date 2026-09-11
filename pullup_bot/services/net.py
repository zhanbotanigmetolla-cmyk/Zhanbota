"""Retry transient network failures on outgoing Telegram API calls.

Telegram occasionally resets the connection mid-request ([Errno 104] Connection
reset by peer) or answers with a 5xx. Without a retry the user just sees nothing
happen after tapping a button, so every API call goes through this middleware.
"""
import asyncio

from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError

from ..config import logger
from . import monitoring

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 0.5  # doubles after each failed attempt
MAX_FLOOD_WAIT = 30  # don't sit and wait on a long flood-control ban


async def retry_middleware(make_request, bot, method):
    """Re-send a Telegram API call a couple of times when the network hiccups."""
    delay = BACKOFF_SECONDS
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await make_request(bot, method)
        except TelegramRetryAfter as e:
            if attempt == MAX_ATTEMPTS or e.retry_after > MAX_FLOOD_WAIT:
                raise
            monitoring.inc("api_retries")
            logger.warning(
                f"[net] {type(method).__name__} flood control, "
                f"waiting {e.retry_after}s (attempt {attempt}/{MAX_ATTEMPTS})"
            )
            await asyncio.sleep(e.retry_after)
        except (TelegramNetworkError, TelegramServerError) as e:
            if attempt == MAX_ATTEMPTS:
                logger.error(f"[net] {type(method).__name__} failed after {attempt} attempts: {e}")
                raise
            monitoring.inc("api_retries")
            logger.warning(
                f"[net] {type(method).__name__} {type(e).__name__}: {e} — "
                f"retrying in {delay}s (attempt {attempt}/{MAX_ATTEMPTS})"
            )
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")  # pragma: no cover
