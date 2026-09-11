import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError

from pullup_bot.services import net


class FakeMethod:
    pass


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Don't actually wait during the backoff."""
    async def instant(_seconds):
        return None
    monkeypatch.setattr(net.asyncio, "sleep", instant)


async def test_returns_result_without_retrying():
    calls = []

    async def make_request(bot, method):
        calls.append(method)
        return "ok"

    assert await net.retry_middleware(make_request, None, FakeMethod()) == "ok"
    assert len(calls) == 1


async def test_retries_connection_reset_then_succeeds():
    attempts = {"n": 0}

    async def make_request(bot, method):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TelegramNetworkError(method=method, message="ClientOSError: [Errno 104] Connection reset by peer")
        return "ok"

    assert await net.retry_middleware(make_request, None, FakeMethod()) == "ok"
    assert attempts["n"] == 2


async def test_gives_up_after_max_attempts():
    attempts = {"n": 0}

    async def make_request(bot, method):
        attempts["n"] += 1
        raise TelegramServerError(method=method, message="Bad Gateway")

    with pytest.raises(TelegramServerError):
        await net.retry_middleware(make_request, None, FakeMethod())
    assert attempts["n"] == net.MAX_ATTEMPTS


async def test_long_flood_wait_is_not_retried():
    attempts = {"n": 0}

    async def make_request(bot, method):
        attempts["n"] += 1
        raise TelegramRetryAfter(method=method, message="Too Many Requests", retry_after=300)

    with pytest.raises(TelegramRetryAfter):
        await net.retry_middleware(make_request, None, FakeMethod())
    assert attempts["n"] == 1
