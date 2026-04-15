from pullup_bot.keyboards import parse_rpe, smart_set_buttons, welcome_new_user_kb


# --- parse_rpe ---

def test_parse_rpe_number():
    assert parse_rpe("5") == 5


def test_parse_rpe_emoji():
    assert parse_rpe("😴 1") == 1
    assert parse_rpe("☠️ 10") == 10


def test_parse_rpe_skip_ru():
    assert parse_rpe("⏭️ Пропустить") == 0


def test_parse_rpe_skip_en():
    assert parse_rpe("⏭️ Skip") == 0


def test_parse_rpe_invalid():
    assert parse_rpe("hello") is None


def test_parse_rpe_empty():
    assert parse_rpe("") is None


def test_parse_rpe_none():
    assert parse_rpe(None) is None


def test_parse_rpe_out_of_range():
    assert parse_rpe("11") is None


def test_parse_rpe_negative_extracts_digit():
    # regex finds "1" in "-1"
    assert parse_rpe("-1") == 1


# --- smart_set_buttons ---

def test_smart_set_buttons_count():
    result = smart_set_buttons(100)
    assert len(result) == 10


def test_smart_set_buttons_sorted():
    result = smart_set_buttons(100)
    assert result == sorted(result)


def test_smart_set_buttons_all_positive():
    result = smart_set_buttons(100)
    assert all(n >= 1 for n in result)


def test_smart_set_buttons_zero_planned():
    result = smart_set_buttons(0)
    assert len(result) == 10
    assert 5 in result


def test_smart_set_buttons_row1_consecutive():
    result = smart_set_buttons(100)
    for i in range(4):
        assert result[i + 1] - result[i] == 1


def test_smart_set_buttons_row2_increasing_gaps():
    result = smart_set_buttons(100)
    gaps = [result[i + 1] - result[i] for i in range(5, 9)]
    assert gaps == sorted(gaps)


def test_smart_set_buttons_small_planned():
    result = smart_set_buttons(30)
    assert all(isinstance(n, int) for n in result)


def test_welcome_new_user_kb_callback_data():
    kb = welcome_new_user_kb("Yedil", 123456789, "ru")
    btn = kb.inline_keyboard[0][0]
    assert btn.callback_data == "welcome_new:123456789"


def test_welcome_new_user_kb_text_length_limit():
    kb = welcome_new_user_kb("ОченьДлинноеИмя" * 20, 1, "ru")
    btn = kb.inline_keyboard[0][0]
    assert len(btn.text.encode("utf-8")) <= 64
