from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 Рассылка откликов"),
                KeyboardButton(text="📄 Мои резюме"),
            ],
            [
                KeyboardButton(text="💬 Ответить работодателям"),
                KeyboardButton(text="🗑️ Очистить отклики"),
            ],
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="📊 Мои отклики"),
            ],
            [
                KeyboardButton(text="🔄 Обновить токен"),
                KeyboardButton(text="⚙️ Помощь"),
            ],
            [
                KeyboardButton(text="📌 Статус задачи"),
            ],
        ],
        resize_keyboard=True,
    )


def auth_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 Войти в HH")],
            [KeyboardButton(text="🔐 Войти через токены")],
        ],
        resize_keyboard=True,
    )


def password_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📨 Получить код на почту/SMS", callback_data="auth_otp")],
            [InlineKeyboardButton(text="🔒 Ввести пароль", callback_data="auth_password")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def resume_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить все резюме", callback_data="update_resumes")],
        ]
    )


def apply_options() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить (по умолчанию)", callback_data="apply_default")],
            [InlineKeyboardButton(text="🔍 С поисковым запросом", callback_data="apply_search")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def apply_confirm(search: str | None = None, excluded: str | None = None) -> InlineKeyboardMarkup:
    parts = []
    if search:
        parts.append(f"Поиск: {search}")
    if excluded:
        parts.append(f"Исключения: {excluded}")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Запустить рассылку", callback_data="apply_go")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def clear_options() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Только отказы", callback_data="clear_discards")],
            [InlineKeyboardButton(text="📅 Старше N дней", callback_data="clear_older")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def logout_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, выйти", callback_data="logout_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="cancel"),
            ],
        ]
    )
