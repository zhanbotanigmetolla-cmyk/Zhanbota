"""Free-text settings input: display names and skip reasons."""
from datetime import timedelta
from types import SimpleNamespace

from pullup_bot import timeutils
from pullup_bot.handlers import settings
from .conftest import insert_test_user


class FakeState:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.cleared = False
        self.state = None

    async def get_data(self):
        return self.data

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.cleared = True
        self.data = {}


class FakeMessage:
    def __init__(self, tg_id, text):
        self.from_user = SimpleNamespace(id=tg_id, username="tester", first_name="Tester")
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
        return self


async def _first_name(conn, tg_id):
    async with conn.execute("SELECT first_name FROM users WHERE tg_id=?", (tg_id,)) as cur:
        return (await cur.fetchone())[0]


async def _streak(conn, tg_id):
    async with conn.execute("SELECT streak FROM users WHERE tg_id=?", (tg_id,)) as cur:
        return (await cur.fetchone())[0]


async def test_name_must_be_three_to_sixty_four_characters(test_db):
    await insert_test_user(test_db, tg_id=1, first_name="Old")
    for bad in ["ab", "x" * 65, "   ", "\x01\x02"]:
        message = FakeMessage(1, bad)
        state = FakeState()
        await settings.set_name_save(message, state)
        assert await _first_name(test_db, 1) == "Old"
        assert not state.cleared
        assert "3" in message.answers[-1][0]


async def test_name_with_markdown_characters_is_saved_and_escaped_in_the_reply(test_db):
    await insert_test_user(test_db, tg_id=1, first_name="Old")
    message = FakeMessage(1, "  Al_ex   *Pro*  ")
    state = FakeState()
    await settings.set_name_save(message, state)
    assert await _first_name(test_db, 1) == "Al_ex *Pro*"
    reply, kwargs = message.answers[0]
    assert kwargs.get("parse_mode") == "Markdown"
    assert "Al\\_ex \\*Pro\\*" in reply
    assert state.cleared


async def test_skip_reason_credits_a_missed_day_only_once(test_db):
    await insert_test_user(test_db, tg_id=1, streak=5)
    missed = (timeutils.today() - timedelta(days=1)).isoformat()
    message = FakeMessage(1, "🤒 Болел *сильно*")
    await settings.skip_reason_save(message, FakeState({"skip_date": missed}))
    assert await _streak(test_db, 1) == 6
    assert "Болел \\*сильно\\*" in message.answers[0][0]
    async with test_db.execute("SELECT exercise FROM workouts WHERE date=?", (missed,)) as cur:
        assert [r[0] for r in await cur.fetchall()] == ["rest"]

    # The same date again only updates the note.
    await settings.skip_reason_save(FakeMessage(1, "Учёба"), FakeState({"skip_date": missed}))
    assert await _streak(test_db, 1) == 6
    async with test_db.execute("SELECT reason FROM streak_recoveries") as cur:
        assert [r[0] for r in await cur.fetchall()] == ["Учёба"]


async def test_skip_reason_on_a_trained_day_adds_no_streak_and_no_rest_row(test_db):
    await insert_test_user(test_db, tg_id=1, streak=5)
    day = (timeutils.today() - timedelta(days=2)).isoformat()
    await test_db.execute(
        "INSERT INTO workouts (user_id,date,exercise,planned,completed) "
        "SELECT id,?,'pullups',30,30 FROM users WHERE tg_id=1", (day,))
    await test_db.commit()
    message = FakeMessage(1, "x" * 300)
    await settings.skip_reason_save(message, FakeState({"skip_date": day}))
    assert await _streak(test_db, 1) == 5
    async with test_db.execute("SELECT exercise FROM workouts WHERE date=?", (day,)) as cur:
        assert [r[0] for r in await cur.fetchall()] == ["pullups"]
    async with test_db.execute("SELECT reason FROM streak_recoveries") as cur:
        assert len((await cur.fetchone())[0]) == settings.MAX_REASON_LEN
