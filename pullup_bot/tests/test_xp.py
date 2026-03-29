from pullup_bot.services.xp import (
    activity_reduction, display, level_info, md_escape, planned_for_day, progress_bar,
)


# --- level_info ---

def test_level_info_zero():
    lvl, name, to_nxt, pct = level_info(0)
    assert lvl == 0
    assert name == "Новичок"
    assert to_nxt == 500
    assert pct == 0


def test_level_info_mid():
    lvl, name, to_nxt, pct = level_info(600)
    assert lvl == 1


def test_level_info_exact_threshold():
    lvl, _, _, _ = level_info(500)
    assert lvl == 1


def test_level_info_high():
    lvl, _, _, _ = level_info(25000)
    assert lvl == 9


# --- progress_bar ---

def test_progress_bar_zero():
    bar = progress_bar(0)
    assert bar == "░" * 10


def test_progress_bar_full():
    bar = progress_bar(100)
    assert bar == "█" * 10


def test_progress_bar_half():
    bar = progress_bar(50)
    assert bar.count("█") == 5
    assert bar.count("░") == 5


def test_progress_bar_custom_length():
    bar = progress_bar(50, length=20)
    assert len(bar) == 20


def test_progress_bar_over_100():
    bar = progress_bar(200)
    assert bar == "█" * 10


# --- planned_for_day ---

def test_planned_medium():
    user = {"base_pullups": 100, "program_day": 0}
    planned, day_type = planned_for_day(user)
    assert planned == 100
    assert day_type == "Средний"


def test_planned_light():
    user = {"base_pullups": 100, "program_day": 1}
    planned, day_type = planned_for_day(user)
    assert planned == 50
    assert day_type == "Лёгкий"


def test_planned_heavy():
    user = {"base_pullups": 100, "program_day": 2}
    planned, day_type = planned_for_day(user)
    assert planned == 114  # int(100 * 1.15)
    assert day_type == "Тяжёлый"


def test_planned_rest():
    user = {"base_pullups": 100, "program_day": 3}
    planned, day_type = planned_for_day(user)
    assert planned == 0
    assert day_type == "Отдых"


def test_planned_wraps_around():
    user = {"base_pullups": 100, "program_day": 7}
    planned, day_type = planned_for_day(user)
    assert day_type == "Средний"


def test_planned_none_program_day():
    user = {"base_pullups": 100, "program_day": None}
    planned, day_type = planned_for_day(user)
    assert day_type == "Средний"


# --- activity_reduction ---

def test_reduction_no_activity():
    assert activity_reduction("", 60) == 1.0
    assert activity_reduction("бег", 0) == 1.0


def test_reduction_running():
    r = activity_reduction("бег", 60)
    assert 0.5 <= r < 1.0


def test_reduction_gym():
    r = activity_reduction("зал спина", 60)
    assert 0.5 <= r < 1.0


def test_reduction_cardio():
    r = activity_reduction("кардио", 60)
    assert 0.5 <= r < 1.0


def test_reduction_floor():
    r = activity_reduction("бег", 600)
    assert r >= 0.5


# --- display ---

def test_display_first_name():
    assert display({"first_name": "Alex", "username": "alex"}) == "Alex"


def test_display_username_fallback():
    assert display({"first_name": "", "username": "alex"}) == "alex"


def test_display_none():
    assert display(None) == "Участник"


def test_display_empty():
    assert display({"first_name": "", "username": ""}) == "Участник"


# --- md_escape ---

def test_md_escape_underscore():
    assert md_escape("test_name") == "test\\_name"


def test_md_escape_star():
    assert md_escape("*bold*") == "\\*bold\\*"


def test_md_escape_plain():
    assert md_escape("hello") == "hello"
