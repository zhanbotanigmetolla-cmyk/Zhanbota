from aiogram.fsm.state import State, StatesGroup


class Guide(StatesGroup):
    step1 = State()
    step2 = State()
    step3 = State()
    step4 = State()
    extra = State()


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


class SetName(StatesGroup):
    enter_name = State()


class BugReport(StatesGroup):
    enter_text = State()


class Login(StatesGroup):
    lang = State()
    enter_code = State()


class DeleteAccount(StatesGroup):
    confirm = State()


class Friends(StatesGroup):
    viewing = State()


class AdminPanel(StatesGroup):
    main           = State()
    user_list      = State()
    user_search    = State()
    user_profile   = State()
    confirm_action = State()
    broadcast      = State()
    mute_duration  = State()
    give_tokens    = State()
    bug_list       = State()
    change_name    = State()
