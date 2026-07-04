from ..config import BASE_COLS, LEVEL_NAMES, LEVEL_THRESHOLDS, PROGRAMS


def display(user) -> str:
    """Return the best available display name for a user row (first_name > username > fallback)."""
    if not user:
        return "Участник"
    name = user["first_name"]
    if name and len(name) >= 2:
        return name
    return user["username"] or "Участник"


def md_escape(text: str) -> str:
    """Escape all Telegram MarkdownV2 special characters in a string."""
    for ch in r"\_*`[]()~>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def level_info(xp: int):
    """Return (level_index, level_name, xp_to_next, progress_pct) for the given XP value."""
    lvl = 0
    for i, t in enumerate(LEVEL_THRESHOLDS[:-1]):
        if xp >= t:
            lvl = i
    name = LEVEL_NAMES[lvl]
    nxt = LEVEL_THRESHOLDS[lvl + 1]
    cur = LEVEL_THRESHOLDS[lvl]
    pct = int((xp - cur) / (nxt - cur) * 100) if nxt > cur else 100
    to_nxt = nxt - xp
    return lvl, name, to_nxt, pct


def progress_bar(pct: int, length: int = 10) -> str:
    """Render a filled/empty block progress bar string for the given percentage."""
    filled = max(0, min(length, int(length * pct / 100)))
    return "█" * filled + "░" * (length - filled)


def user_base(user, exercise: str = "pullups") -> int:
    """Return the user's daily base for the given exercise (0 = not set up yet)."""
    return user[BASE_COLS[exercise]] or 0


def day_type_for(user) -> tuple:
    """Return (day_type_name, coeff) for the user's current position in their program cycle."""
    program_day = user["program_day"] or 0
    wave = PROGRAMS.get(user["program_type"] or "standard", PROGRAMS["standard"])
    return wave[program_day % 7]


def planned_for_day(user, exercise: str = "pullups"):
    """Return (planned_count, day_type_name) for the user's cycle position and exercise."""
    name, coeff = day_type_for(user)
    return int(user_base(user, exercise) * coeff), name
