from pullup_bot.i18n import t, day_name


# --- t() ---

def test_t_ru_button():
    assert t("btn_train", "ru") == "🏋️ Тренировка"


def test_t_en_button():
    assert t("btn_train", "en") == "🏋️ Training"


def test_t_unknown_lang_falls_back_to_ru():
    assert t("btn_train", "xx") == t("btn_train", "ru")


def test_t_unknown_key_returns_key():
    assert t("nonexistent_key_xyz", "ru") == "nonexistent_key_xyz"


def test_t_kwargs():
    result = t("train_goal", "en", planned=100)
    assert "100" in result


def test_t_kwargs_ru():
    result = t("welcome_user", "ru", name="Alex", max_pullups=15, base=45, level="Silver I")
    assert "Alex" in result
    assert "45" in result
    assert "15" in result


# --- day_name() ---

def test_day_name_ru():
    assert day_name("Средний", "ru") == "Средний"
    assert day_name("Тяжёлый", "ru") == "Тяжёлый"


def test_day_name_en():
    assert day_name("Средний", "en") == "Medium"
    assert day_name("Отдых", "en") == "Rest"
    assert day_name("Плотность", "en") == "Density"


def test_day_name_unknown():
    assert day_name("Unknown", "en") == "Unknown"
