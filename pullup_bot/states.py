from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    name = State()
    weight = State()
    base = State()
    start_day = State()


class Training(StatesGroup):
    active = State()
    rest_day = State()
    cancel_confirm = State()
    rpe = State()
    activity = State()
    act_mins = State()
    notes = State()
    freeze_confirm = State()


class Logout(StatesGroup):
    confirm = State()


class Settings(StatesGroup):
    viewing = State()
    pick_lang = State()


class EditDay(StatesGroup):
    pick_date = State()
    pick_done = State()
    pick_rpe = State()


class SkipReason(StatesGroup):
    pick_date = State()
    enter_reason = State()


class SetNotify(StatesGroup):
    enter_time = State()


class SetBase(StatesGroup):
    enter_base = State()


class SetWeight(StatesGroup):
    enter_weight = State()


class BugReport(StatesGroup):
    enter_text = State()


class Login(StatesGroup):
    lang = State()
    enter_code = State()


class DeleteAccount(StatesGroup):
    confirm = State()


class Friends(StatesGroup):
    viewing = State()
