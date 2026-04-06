import re
from typing import Optional

from aiogram import types
from aiogram.types import (InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from .config import START_MENU_LABEL
from .i18n import t


def main_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("btn_train", lang)))
    b.row(KeyboardButton(text=t("btn_stats", lang)), KeyboardButton(text=t("btn_history", lang)))
    b.row(KeyboardButton(text=t("btn_friends", lang)), KeyboardButton(text=t("btn_ai", lang)))
    b.row(KeyboardButton(text=t("btn_settings", lang)), KeyboardButton(text=t("btn_bug", lang)))
    b.row(KeyboardButton(text=t("btn_leaderboard", lang)), KeyboardButton(text=t("btn_entrance", lang)))
    return b.as_markup(resize_keyboard=True, persistent=True)


def landing_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("btn_login", lang)))
    b.row(KeyboardButton(text=t("btn_guide", lang)), KeyboardButton(text=t("btn_about", lang)))
    return b.as_markup(resize_keyboard=True)


def settings_kb(lang: str = "ru", is_admin: bool = False) -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("btn_notify_time", lang)), KeyboardButton(text=t("btn_change_base", lang)))
    b.row(KeyboardButton(text=t("btn_change_weight", lang)), KeyboardButton(text=t("btn_edit_day", lang)))
    b.row(KeyboardButton(text=t("btn_skip_reason", lang)), KeyboardButton(text=t("btn_logout", lang)))
    b.row(KeyboardButton(text=t("btn_language", lang)), KeyboardButton(text=t("btn_delete_account", lang)))
    if is_admin:
        b.row(KeyboardButton(text="🛡 Панель администратора"))
    b.row(KeyboardButton(text=t("btn_back", lang)))
    return b.as_markup(resize_keyboard=True)


def smart_set_buttons(planned: int) -> list:
    if planned <= 0:
        return [5, 8, 10, 12, 15, 20, 25, 30]
    avg = max(3, planned // 10)
    return sorted(set([
        max(3, avg - 4), max(3, avg - 2), avg,
        avg + 2, avg + 4, avg + 7, avg + 10, avg + 15,
    ]))[:8]


def training_kb(sets: list, planned: int = 0, lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    for n in smart_set_buttons(planned):
        b.button(text=str(n))
    b.adjust(4)
    b.row(KeyboardButton(text=t("btn_undo", lang)),
          KeyboardButton(text=t("btn_manual", lang)))
    b.row(KeyboardButton(text=t("btn_finish", lang)),
          KeyboardButton(text=t("btn_cancel_train", lang)))
    return b.as_markup(resize_keyboard=True)


def rpe_menu_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="😴 1"), KeyboardButton(text="😌 2"),
          KeyboardButton(text="🙂 3"), KeyboardButton(text="😐 4"),
          KeyboardButton(text="😤 5"))
    b.row(KeyboardButton(text="😓 6"), KeyboardButton(text="🥵 7"),
          KeyboardButton(text="😰 8"), KeyboardButton(text="💀 9"),
          KeyboardButton(text="☠️ 10"))
    b.row(KeyboardButton(text=t("btn_skip", lang)))
    return b.as_markup(resize_keyboard=True, one_time_keyboard=True)



LANG_TOGGLE_BTN = "🇷🇺 Русский  |  🇬🇧 English"  # kept for backward compat
LANG_RU_BTN = "🇷🇺 Русский"
LANG_EN_BTN = "🇬🇧 English"
LANG_BACK_BILINGUAL = "◀️ Назад | Back"


def lang_kb(show_back: bool = False) -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=LANG_RU_BTN), KeyboardButton(text=LANG_EN_BTN))
    if show_back:
        b.row(KeyboardButton(text=LANG_BACK_BILINGUAL))
    return b.as_markup(resize_keyboard=True)


def rest_day_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("rest_day_train", lang)),
          KeyboardButton(text=t("rest_day_rest", lang)))
    return b.as_markup(resize_keyboard=True)


def cancel_confirm_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("train_yes_cancel", lang)),
          KeyboardButton(text=t("train_continue", lang)))
    return b.as_markup(resize_keyboard=True)


def delete_confirm_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("delete_confirm_yes", lang)),
          KeyboardButton(text=t("delete_confirm_no", lang)))
    return b.as_markup(resize_keyboard=True)


def freeze_confirm_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("freeze_yes_btn", lang)),
          KeyboardButton(text=t("freeze_no_btn", lang)))
    return b.as_markup(resize_keyboard=True)


def logout_confirm_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=t("confirm_yes", lang)),
          KeyboardButton(text=t("confirm_no", lang)))
    return b.as_markup(resize_keyboard=True)


def skip_reason_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    for key in ["reason_study", "reason_sick", "reason_overtrain",
                "reason_travel", "reason_weather", "reason_gym"]:
        b.button(text=t(key, lang))
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)


def activity_reply_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    if lang == "en":
        labels = ["🏃 Running/Cardio", "🏋️ Gym", "⏭️ Skip"]
    else:
        labels = ["🏃 Бег/Кардио", "🏋️ Зал", "⏭️ Пропустить"]
    for label in labels:
        b.button(text=label)
    b.adjust(3)
    return b.as_markup(resize_keyboard=True, one_time_keyboard=True)


def history_nav_kb(offset: int, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    prev_label = "← Пред. неделя" if lang == "ru" else "← Prev week"
    next_label = "Сл. неделя →" if lang == "ru" else "Next week →"
    b.button(text=prev_label, callback_data=f"hist_{offset - 1}")
    if offset < 0:
        b.button(text=next_label, callback_data=f"hist_{offset + 1}")
    b.adjust(2)
    return b.as_markup()


def _truncate_utf8(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    ellipsis = "…"
    if len(ellipsis.encode("utf-8")) > max_bytes:
        return ""
    trimmed = text
    while trimmed and len((trimmed + ellipsis).encode("utf-8")) > max_bytes:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + ellipsis) if trimmed else ""


def welcome_new_user_kb(name: str, new_tg_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    clean_name = " ".join((name or "").split())
    if not clean_name:
        clean_name = "атлет" if lang == "ru" else "athlete"

    prefix = "Поприветствовать " if lang == "ru" else "Welcome "
    suffix = " 🤜🤛"
    name_budget = 64 - len((prefix + suffix).encode("utf-8"))
    safe_name = _truncate_utf8(clean_name, name_budget)
    if not safe_name:
        safe_name = "атлета" if lang == "ru" else "new member"
    button_text = f"{prefix}{safe_name}{suffix}"
    if len(button_text.encode("utf-8")) > 64:
        button_text = _truncate_utf8(button_text, 64)

    b.button(text=button_text, callback_data=f"welcome_new:{new_tg_id}")
    return b.as_markup()


def parse_rpe(text: str) -> Optional[int]:
    if not text:
        return None
    t = text.strip().lower()
    if "пропустить" in t or "skip" in t:
        return 0
    m = re.search(r"\d+", t)
    if not m:
        return None
    v = int(m.group(0))
    return v if 0 <= v <= 10 else None


# ── Admin panel inline keyboards ────────────────────────────────────────────

def admin_panel_main_kb(maintenance_on: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👥 Пользователи", callback_data="ap:users:0")
    b.button(text="📊 Статистика", callback_data="ap:stats")
    b.button(text="🐛 Баг-репорты", callback_data="ap:bugs:0")
    b.button(text="📢 Рассылка", callback_data="ap:broadcast")
    maint_label = "🔧 Техобслуживание: ВКЛ" if maintenance_on else "🔧 Техобслуживание: ВЫКЛ"
    b.button(text=maint_label, callback_data="ap:maintenance")
    b.button(text="🔄 Перезапустить бота", callback_data="ap:restart")
    b.button(text="✖ Закрыть панель", callback_data="ap:close")
    b.adjust(2, 2, 1, 1, 1)
    return b.as_markup()


def admin_users_kb(users: list, page: int, total: int, per_page: int = 10) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for u in users:
        name = (u["username"] or u["first_name"] or "???")[:20]
        if u["is_banned"]:
            status = "🔴"
        elif u["muted_until"]:
            status = "🔇"
        else:
            status = "🟢"
        label = f"{status} {name} | Lv{u['level']} | 🔥{u['streak']}"
        b.button(text=label[:64], callback_data=f"ap:user:{u['tg_id']}")
    b.adjust(1)
    total_pages = max(1, (total + per_page - 1) // per_page)
    nav = []
    if page > 0:
        nav.append(("◀ Пред.", f"ap:users:{page - 1}"))
    nav.append((f"{page + 1}/{total_pages}", "ap:main"))
    if (page + 1) * per_page < total:
        nav.append(("След. ▶", f"ap:users:{page + 1}"))
    for text_nav, cb in nav:
        b.button(text=text_nav, callback_data=cb)
    b.button(text="🔍 Поиск", callback_data="ap:search")
    b.button(text="◀◀ Главная", callback_data="ap:main")
    b.adjust(1)
    return b.as_markup()


def admin_user_profile_kb(tg_id: int, is_banned: bool, muted: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_banned:
        b.button(text="✅ Разбанить", callback_data=f"ap:unban:{tg_id}")
    else:
        b.button(text="🚫 Забанить", callback_data=f"ap:ban:{tg_id}")
    if muted:
        b.button(text="🔈 Размутить", callback_data=f"ap:unmute:{tg_id}")
    else:
        b.button(text="🔇 Замутить", callback_data=f"ap:mute:{tg_id}")
    b.button(text="💧 Сбросить стрик", callback_data=f"ap:rst_streak:{tg_id}")
    b.button(text="📉 Сбросить XP/уровень", callback_data=f"ap:rst_xp:{tg_id}")
    b.button(text="🧊 Дать/убрать токены", callback_data=f"ap:tokens:{tg_id}")
    b.button(text="🗑 Удалить аккаунт", callback_data=f"ap:delete:{tg_id}")
    b.button(text="◀ К списку", callback_data="ap:back_to_users")
    b.adjust(2, 2, 1, 1, 1)
    return b.as_markup()


def admin_confirm_kb(action: str, tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=f"ap:confirm:{action}:{tg_id}")
    b.button(text="❌ Отмена", callback_data="ap:cancel_confirm")
    b.adjust(2)
    return b.as_markup()


def admin_confirm_restart_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Перезапустить", callback_data="ap:confirm_restart")
    b.button(text="❌ Отмена", callback_data="ap:main")
    b.adjust(2)
    return b.as_markup()


def admin_bugs_kb(reports: list, page: int, has_more: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in reports:
        status = "🔴" if r["status"] == "new" else "✅"
        uname = (r["username"] or "?")[:15]
        label = f"{status} #{r['id']} — {uname}"
        b.button(text=label, callback_data=f"ap:fix_bug:{r['id']}")
    b.adjust(1)
    if page > 0:
        b.button(text="◀ Пред.", callback_data=f"ap:bugs:{page - 1}")
    if has_more:
        b.button(text="След. ▶", callback_data=f"ap:bugs:{page + 1}")
    b.button(text="◀◀ Главная", callback_data="ap:main")
    b.adjust(1)
    return b.as_markup()
