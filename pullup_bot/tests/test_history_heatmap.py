from pullup_bot.handlers.history import _day_cell, _month_heatmap


def _tr(planned, completed):
    return {"exercise": "pullups", "planned": planned, "completed": completed}


# --- _day_cell ---

def test_day_cell_target_hit():
    assert _day_cell([_tr(50, 55)]) == "🟩"


def test_day_cell_partial():
    assert _day_cell([_tr(50, 20)]) == "🟨"


def test_day_cell_started_but_zero_reps():
    assert _day_cell([_tr(50, 0)]) == "⬜"


def test_day_cell_rest():
    assert _day_cell([{"exercise": "rest", "planned": 0, "completed": 0}]) == "😴"


def test_day_cell_no_data():
    assert _day_cell([]) == "⬜"


def test_day_cell_multi_exercise_one_missed_is_partial():
    rows = [_tr(50, 50), {"exercise": "squats", "planned": 80, "completed": 60}]
    assert _day_cell(rows) == "🟨"


def test_day_cell_multi_exercise_all_hit():
    rows = [_tr(50, 50), {"exercise": "squats", "planned": 80, "completed": 80}]
    assert _day_cell(rows) == "🟩"


# --- _month_heatmap (past months only, so results don't depend on today) ---

def test_heatmap_past_month_full_grid():
    # June 2026 starts on a Monday: no padding, 30 days → 5 rows (7+7+7+7+2)
    out = _month_heatmap({}, 2026, 6, "en")
    lines = out.split("\n")
    assert lines[0] == "*June 2026*"
    assert len(lines) == 6
    assert out.count("⬜") == 30
    assert "▫️" not in out


def test_heatmap_padding_aligns_weekdays():
    # May 2026 starts on a Friday (weekday 4) → 4 leading pad cells
    out = _month_heatmap({}, 2026, 5, "ru")
    first_row = out.split("\n")[1]
    assert first_row.startswith("▫️" * 4)
    assert out.count("⬜") == 31


def test_heatmap_statuses_land_on_right_days():
    rows = {
        "2026-06-01": [_tr(50, 55)],                                    # hit
        "2026-06-02": [_tr(50, 20)],                                    # partial
        "2026-06-03": [{"exercise": "rest", "planned": 0, "completed": 0}],
    }
    out = _month_heatmap(rows, 2026, 6, "ru")
    lines = out.split("\n")
    assert lines[0] == "*Июнь 2026*"
    assert lines[1] == "🟩🟨😴⬜⬜⬜⬜"
