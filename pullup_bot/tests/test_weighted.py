import json
from datetime import date, timedelta

import pytest

from pullup_bot.config import (BASE_COLS, WEIGHT_COLS, expected_rpe, is_weighted,
                               weight_multiplier, xp_for)
from pullup_bot.handlers.training import (_apply_rpe_adjustment,
                                          _check_weekly_progression,
                                          _check_weighted_progression)
from pullup_bot.keyboards import weight_choices
from .conftest import insert_test_user


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


async def add_session(conn, user_id, exercise, day_offset, planned, completed,
                      rpe=0, day_type="Средний", weight=0):
    await conn.execute(
        "INSERT INTO workouts (user_id, date, exercise, planned, completed, "
        "sets_json, rpe, day_type, weight_kg) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, days_ago(day_offset), exercise, planned, completed,
         json.dumps([completed]), rpe, day_type, weight))
    await conn.commit()


# ── XP ───────────────────────────────────────────────────────────────────────

def test_added_load_is_worth_more_xp():
    assert xp_for("pullups", 10) == 10
    assert xp_for("pullups_weighted", 10, 0) == 10
    assert xp_for("pullups_weighted", 10, 20) == 16   # +3%/kg
    assert xp_for("dips_weighted", 10, 20) == 12      # 0.75 base rate


def test_xp_load_is_capped():
    """A mistyped load must not mint unbounded XP."""
    assert weight_multiplier(50) == weight_multiplier(500)
    assert xp_for("pullups_weighted", 10, 500) == 25


def test_bodyweight_exercises_ignore_a_stray_weight():
    """Only weighted variants scale — a weight on a bodyweight row changes nothing."""
    assert xp_for("pullups", 10, 20) == 10
    assert not is_weighted("pullups")
    assert is_weighted("pullups_weighted")


def test_weight_choices_never_go_negative():
    assert min(weight_choices(0)) == 0
    assert weight_choices(2.5) == [0.0, 2.5, 5.0, 7.5]


# ── RPE judged against the day type ──────────────────────────────────────────

def test_expected_rpe_rises_with_day_difficulty():
    assert expected_rpe("Лёгкий") < expected_rpe("Средний") < expected_rpe("Тяжёлый")


@pytest.mark.asyncio
async def test_hard_day_at_rpe_8_does_not_cut_the_base(test_db):
    """RPE 8 on a Тяжёлый day is the plan working, not a reason to back off."""
    await insert_test_user(test_db, tg_id=1, base=100)
    for i, offset in enumerate([1, 2, 3]):
        await add_session(test_db, 1, "pullups", offset, 100, 100,
                          rpe=8, day_type="Тяжёлый")
    new_base, _, delta = await _apply_rpe_adjustment(1, 1, "pullups", 100)
    assert new_base is None
    assert delta == 0.0


@pytest.mark.asyncio
async def test_easy_day_at_rpe_8_does_cut_the_base(test_db):
    """The same RPE 8 on a Лёгкий day means the load really is too high."""
    await insert_test_user(test_db, tg_id=1, base=100)
    for offset in [1, 2, 3]:
        await add_session(test_db, 1, "pullups", offset, 100, 100,
                          rpe=8, day_type="Лёгкий")
    new_base, _, delta = await _apply_rpe_adjustment(1, 1, "pullups", 100)
    assert delta == 3.0
    assert new_base == 95  # −5%


@pytest.mark.asyncio
async def test_training_easier_than_prescribed_raises_the_base(test_db):
    await insert_test_user(test_db, tg_id=1, base=100)
    for offset in [1, 2, 3]:
        await add_session(test_db, 1, "pullups", offset, 100, 100,
                          rpe=5, day_type="Тяжёлый")
    new_base, _, _ = await _apply_rpe_adjustment(1, 1, "pullups", 100)
    assert new_base == 103  # +3%


# ── Weekly progression ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_abandoned_session_no_longer_blocks_progression(test_db):
    """A 0/139 row is a session never started — it must not count as 0%."""
    await insert_test_user(test_db, tg_id=1, base=100)
    await add_session(test_db, 1, "pullups", 6, 100, 0, rpe=0)  # abandoned
    for offset in [1, 2, 3, 4, 5]:
        await add_session(test_db, 1, "pullups", offset, 100, 100, rpe=6)
    assert await _check_weekly_progression(1, 1, "pullups", 100) == 105


@pytest.mark.asyncio
async def test_progression_needs_five_sessions(test_db):
    await insert_test_user(test_db, tg_id=1, base=100)
    for offset in [1, 2, 3, 4]:
        await add_session(test_db, 1, "pullups", offset, 100, 100, rpe=6)
    assert await _check_weekly_progression(1, 1, "pullups", 100) is None


@pytest.mark.asyncio
async def test_abandoned_exercise_does_not_progress_on_stale_data(test_db):
    await insert_test_user(test_db, tg_id=1, base=100)
    for offset in [40, 41, 42, 43, 44]:
        await add_session(test_db, 1, "pullups", offset, 100, 100, rpe=6)
    assert await _check_weekly_progression(1, 1, "pullups", 100) is None


# ── Double progression for weighted work ─────────────────────────────────────

@pytest.mark.asyncio
async def test_hitting_the_plan_adds_a_plate_and_drops_reps(test_db):
    await insert_test_user(test_db, tg_id=1, base_pullups_weighted=30,
                           weight_pullups_weighted=10)
    for offset in [1, 2, 3, 4, 5]:
        await add_session(test_db, 1, "pullups_weighted", offset, 30, 30,
                          rpe=6, weight=10)
    kind, new_base, new_weight = await _check_weighted_progression(
        1, 1, "pullups_weighted", 30, 10)
    assert kind == "weight_up"
    assert new_weight == 12.5
    assert new_base == 27  # target eases 10% for the heavier load

    async with test_db.execute(
            "SELECT weight_pullups_weighted, base_pullups_weighted, "
            "best_weight_pullups_weighted FROM users WHERE tg_id=1") as cur:
        row = await cur.fetchone()
    assert (row[0], row[1], row[2]) == (12.5, 27, 12.5)


@pytest.mark.asyncio
async def test_falling_short_strips_a_plate(test_db):
    await insert_test_user(test_db, tg_id=1, base_pullups_weighted=30,
                           weight_pullups_weighted=10)
    for offset in [1, 2, 3, 4, 5]:
        await add_session(test_db, 1, "pullups_weighted", offset, 30, 15,
                          rpe=9, weight=10)
    kind, new_base, new_weight = await _check_weighted_progression(
        1, 1, "pullups_weighted", 30, 10)
    assert kind == "weight_down"
    assert new_weight == 7.5
    assert new_base == 30  # rep target untouched


@pytest.mark.asyncio
async def test_middling_completion_builds_reps_at_the_same_load(test_db):
    await insert_test_user(test_db, tg_id=1, base_pullups_weighted=30,
                           weight_pullups_weighted=10)
    for offset in [1, 2, 3, 4, 5]:
        await add_session(test_db, 1, "pullups_weighted", offset, 30, 26,
                          rpe=6, weight=10)
    kind, new_base, new_weight = await _check_weighted_progression(
        1, 1, "pullups_weighted", 30, 10)
    assert kind == "reps"
    assert new_weight == 10
    assert new_base == 31  # +5%


@pytest.mark.asyncio
async def test_load_never_drops_below_bodyweight(test_db):
    await insert_test_user(test_db, tg_id=1, base_pullups_weighted=30,
                           weight_pullups_weighted=0)
    for offset in [1, 2, 3, 4, 5]:
        await add_session(test_db, 1, "pullups_weighted", offset, 30, 10,
                          rpe=9, weight=0)
    assert await _check_weighted_progression(1, 1, "pullups_weighted", 30, 0) is None
