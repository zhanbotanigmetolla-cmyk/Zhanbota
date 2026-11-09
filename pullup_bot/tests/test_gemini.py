from datetime import timedelta
from types import SimpleNamespace

import pytest

from pullup_bot.services import gemini


class FakeClient:
    def __init__(self):
        self.error = None
        self.calls = []
        self.aio = SimpleNamespace(chats=SimpleNamespace(create=self.create))

    def create(self, model, **kwargs):
        async def send_message(message):
            self.calls.append((model, message))
            error = self.error.get(model) if isinstance(self.error, dict) else self.error
            if error:
                raise error
            return SimpleNamespace(text="Recovered response")
        return SimpleNamespace(send_message=send_message)


@pytest.fixture
def manager(monkeypatch, tmp_path):
    client = FakeClient()
    clock = SimpleNamespace(value=1000.0)
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: client)
    monkeypatch.setattr(gemini, "_STATE_FILE", str(tmp_path / "gemini-state.json"))
    monkeypatch.setattr(gemini, "time", SimpleNamespace(monotonic=lambda: clock.value))
    return gemini.APIKeyManager(["fake-test-key"]), client, clock


@pytest.mark.asyncio
async def test_temporary_outage_recovers_after_cooldown_without_daily_block(manager):
    api, client, clock = manager
    client.error = RuntimeError("503 UNAVAILABLE")

    assert await api.chat("system", [], "hello") == ("", "")
    assert not api.is_daily_exhausted()
    assert not api._exhausted
    assert len(client.calls) == len(gemini.TIERS)

    client.error = None
    assert await api.chat("system", [], "hello again") == ("", "")
    assert len(client.calls) == len(gemini.TIERS)

    clock.value += gemini.TRANSIENT_COOLDOWN_SECONDS + 1
    assert await api.chat("system", [], "retry") == ("Recovered response", gemini.TIERS[0])
    assert api.daily_count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error", ["429 RESOURCE_EXHAUSTED", "429 quota GenerateRequestsPerMinutePerModel"])
async def test_unknown_or_minute_quota_can_retry_same_day(manager, error):
    api, client, clock = manager
    client.error = RuntimeError(error)

    assert await api.chat("system", [], "hello") == (gemini.RATE_LIMIT_MINUTE, "")
    assert not api.is_daily_exhausted()
    assert not api._exhausted

    client.error = None
    clock.value += gemini.RATE_LIMIT_COOLDOWN_SECONDS + 1
    assert await api.chat("system", [], "retry") == ("Recovered response", gemini.TIERS[0])


@pytest.mark.asyncio
async def test_confirmed_daily_quota_persists_and_resets_next_day(manager, monkeypatch):
    api, client, clock = manager
    client.error = RuntimeError("429 quota GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    assert await api.chat("system", [], "hello") == (gemini.RATE_LIMIT_DAILY, "")
    assert api.is_daily_exhausted()
    restored = gemini.APIKeyManager(["fake-test-key"])
    assert restored.is_daily_exhausted()

    next_day = api._count_date + timedelta(days=1)
    monkeypatch.setattr(gemini, "local_today", lambda: next_day)
    client.error = None
    assert not restored.is_daily_exhausted()
    assert await restored.chat("system", [], "retry") == ("Recovered response", gemini.TIERS[0])


@pytest.mark.asyncio
async def test_unrelated_api_error_does_not_consume_daily_quota(manager):
    api, client, clock = manager
    client.error = RuntimeError("400 Unable to generate content")

    assert await api.chat("system", [], "hello") == ("", "")
    assert not api.is_daily_exhausted()
    assert not api._exhausted


@pytest.mark.asyncio
async def test_daily_quota_on_one_tier_does_not_make_outage_on_other_tiers_permanent(manager):
    api, client, clock = manager
    client.error = {model: RuntimeError("503 UNAVAILABLE") for model in gemini.TIERS}
    client.error[gemini.TIERS[0]] = RuntimeError("429 quota per day exceeded")

    assert await api.chat("system", [], "hello") == ("", "")
    assert api._exhausted == {(0, 0)}
    assert not api.is_daily_exhausted()

    client.error = None
    clock.value += gemini.TRANSIENT_COOLDOWN_SECONDS + 1
    assert await api.chat("system", [], "retry") == ("Recovered response", gemini.TIERS[1])
