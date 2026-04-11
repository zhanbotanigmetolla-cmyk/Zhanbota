from ..config import LEVEL_NAMES, LEVEL_THRESHOLDS, WAVE


def display(user) -> str:
    if not user:
        return "Участник"
    name = user["first_name"]
    if name and len(name) >= 2:
        return name
    return user["username"] or "Участник"


def md_escape(text: str) -> str:
    for ch in r"\_*`[]()~>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def level_info(xp: int):
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
    filled = max(0, min(length, int(length * pct / 100)))
    return "█" * filled + "░" * (length - filled)


def planned_for_day(user):
    base = user["base_pullups"]
    program_day = user["program_day"] or 0
    name, coeff = WAVE[program_day % 7]
    return int(base * coeff), name


def weekly_chart(workouts: list, lang: str = "ru") -> str:
    """Build a 7-row ASCII bar chart from a list of workout rows (last 7 days, oldest first)."""
    BAR_HEIGHT = 5
    if not workouts:
        return ""
    max_done = max((r["completed"] for r in workouts), default=1) or 1
    lines = []
    for r in workouts:
        done = r["completed"]
        planned = r["planned"]
        filled = round(done / max_done * BAR_HEIGHT)
        bar = "█" * filled + "░" * (BAR_HEIGHT - filled)
        date_label = r["date"][5:]  # MM-DD
        status = "✅" if planned > 0 and done >= planned else ("😴" if planned == 0 else "❌")
        lines.append(f"`{status} {date_label}  [{bar}]  {done}`")
    return "\n".join(lines)


def activity_reduction(extra_activity: str, minutes: int) -> float:
    if not extra_activity or minutes == 0:
        return 1.0
    a = extra_activity.lower()
    has_run = "бег" in a or "run" in a
    has_gym = "зал" in a or "gym" in a
    if has_run and has_gym:
        r = min(0.6, minutes / 60 * 0.38)
    elif has_run:
        r = min(0.38, minutes / 60 * 0.22)
    elif has_gym:
        r = min(0.5, minutes / 60 * 0.3)
    else:
        r = min(0.3, minutes / 60 * 0.15)
    return max(0.5, 1.0 - r)
