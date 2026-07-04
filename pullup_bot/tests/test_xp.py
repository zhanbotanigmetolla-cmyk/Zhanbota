from pullup_bot.config import xp_for
from pullup_bot.services.xp import (
    day_type_for, display, level_info, md_escape, planned_for_day, progress_bar,
    user_base,
)


# --- level_info ---

def test_level_info_zero():
    lvl, name, to_nxt, pct = level_info(0)
    assert lvl == 0
    assert name == "Silver I"
    assert to_nxt == 500
    assert pct == 0


def test_level_info_mid():
    lvl, name, to_nxt, pct = level_info(600)
    assert lvl == 1


def test_level_info_exact_threshold():
    lvl, _, _, _ = level_info(500)
    assert lvl == 1


def test_level_info_high():
    # 25000 XP: >= 23000 (Master Guardian II, index 11), < 29000
    lvl, name, _, _ = level_info(25000)
    assert lvl == 11
    assert name == "Master Guardian II"


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


# --- planned_for_day / user_base / day_type_for ---

def _user(**kw):
    base = {"base_pullups": 100, "base_pushups": 0, "base_dips": 0,
            "program_day": 0, "program_type": "standard"}
    base.update(kw)
    return base


def test_planned_medium():
    planned, day_type = planned_for_day(_user())
    assert planned == 100
    assert day_type == "Средний"


def test_planned_light():
    planned, day_type = planned_for_day(_user(program_day=1))
    assert planned == 50
    assert day_type == "Лёгкий"


def test_planned_heavy():
    planned, day_type = planned_for_day(_user(program_day=2))
    assert planned == 114  # int(100 * 1.15)
    assert day_type == "Тяжёлый"


def test_planned_rest():
    planned, day_type = planned_for_day(_user(program_day=3))
    assert planned == 0
    assert day_type == "Отдых"


def test_planned_wraps_around():
    planned, day_type = planned_for_day(_user(program_day=7))
    assert day_type == "Средний"


def test_planned_none_program_day():
    planned, day_type = planned_for_day(_user(program_day=None, program_type=None))
    assert day_type == "Средний"


def test_planned_beginner_program():
    planned, day_type = planned_for_day(_user(program_type="beginner"))
    assert planned == 60
    assert day_type == "Лёгкий"


def test_planned_unknown_program_falls_back_to_standard():
    planned, day_type = planned_for_day(_user(program_type="bogus"))
    assert planned == 100
    assert day_type == "Средний"


def test_planned_per_exercise():
    u = _user(base_pushups=200, base_dips=40)
    assert planned_for_day(u, "pushups")[0] == 200
    assert planned_for_day(u, "dips")[0] == 40
    assert planned_for_day(u, "pullups")[0] == 100


def test_user_base_unset_is_zero():
    assert user_base(_user(), "pushups") == 0
    assert user_base(_user(base_dips=None), "dips") == 0


def test_day_type_for_rest():
    name, coeff = day_type_for(_user(program_day=3))
    assert name == "Отдых"
    assert coeff == 0.0


# --- xp_for weights ---

def test_xp_for_pullups():
    assert xp_for("pullups", 100) == 100


def test_xp_for_dips():
    assert xp_for("dips", 100) == 75


def test_xp_for_pushups():
    assert xp_for("pushups", 100) == 50


def test_xp_for_rounding():
    assert xp_for("dips", 1) == 1      # 0.75 → 1
    assert xp_for("pushups", 1) == 0   # 0.5 → 0 (banker's rounding)
    assert xp_for("pushups", 3) == 2   # 1.5 → 2


def test_xp_for_rest_is_zero():
    assert xp_for("rest", 50) == 0


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
