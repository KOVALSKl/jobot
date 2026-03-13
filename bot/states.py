from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_password_choice = State()
    waiting_for_password = State()
    auth_in_progress = State()
    waiting_for_tokens = State()


class ApplyStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_excluded = State()
    waiting_for_exclude_mode = State()
    waiting_for_partial_confirm = State()
    waiting_for_message = State()
    confirm = State()


class ReplyStates(StatesGroup):
    waiting_for_message = State()


class ClearStates(StatesGroup):
    waiting_for_days = State()


class ApiCallStates(StatesGroup):
    waiting_for_input = State()
