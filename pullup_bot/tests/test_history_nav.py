from types import SimpleNamespace

from pullup_bot.handlers import history


async def test_history_nav_ignores_malformed_callback_data(test_db):
    answered = []

    async def answer(*args, **kwargs):
        answered.append(True)

    callback = SimpleNamespace(data="hist_oops", from_user=SimpleNamespace(id=1),
                               message=None, answer=answer)
    await history.history_nav(callback)
    assert answered == [True]
