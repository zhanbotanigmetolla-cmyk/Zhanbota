from aiogram.fsm.state import State, StatesGroup


class Guide(StatesGroup):
    step1 = State()
    step2 = State()
    step3 = State()
    step4 = State()
    extra = State()


class About(StatesGroup):
    page2 = State()
    page3 = State()


class Reg(StatesGroup):
    name = State()
    max_pullups = State()


class Training(StatesGroup):
    pick_exercise = State()
    setup_base = State()
    active = State()
    rest_day = State()
    cancel_confirm = State()
    rpe = State()


class Logout(StatesGroup):
    confirm = State()


class Settings(StatesGroup):
    viewing = State()
    pick_lang = State()


class EditDay(StatesGroup):
    pick_date     = State()
    pick_exercise = State()
    pick_done     = State()
    pick_rpe      = State()


class SkipReason(StatesGroup):
    pick_date = State()
    enter_reason = State()


class SetNotify(StatesGroup):
    enter_time = State()


class SetBase(StatesGroup):
    pick_exercise = State()
    enter_base = State()



class SetName(StatesGroup):
    enter_name = State()


class BugReport(StatesGroup):
    enter_text = State()


class Login(StatesGroup):
    lang = State()
    enter_code = State()


class DeleteAccount(StatesGroup):
    confirm = State()


class AIChat(StatesGroup):
    chatting = State()


class Friends(StatesGroup):
    viewing = State()


class SelectProgram(StatesGroup):
    pick = State()


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
