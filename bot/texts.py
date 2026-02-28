"""Централизованные текстовые шаблоны сообщений бота."""

from __future__ import annotations


NEGOTIATION_STATES: dict[str, str] = {
    "response": "📤 Отклик",
    "invitation": "📩 Приглашение",
    "discard": "⛔ Отказ",
    "phone_screen": "📞 Телефонное интервью",
    "interview": "💬 Интервью",
    "hired": "💼 Выход на работу",
}

TEXTS: dict[str, str] = {
    # ── Common ─────────────────────────────────────────────
    "common.not_authorized": "⚠️ Вы не авторизованы. Используйте /start",
    "common.error": "❌ Ошибка: {error}",
    "common.invalid_number": "❌ Введите число.",
    "common.empty_message": "❌ Сообщение не может быть пустым.",

    # ── Middleware ──────────────────────────────────────────
    "middleware.no_access": "⛔ У вас нет доступа к этому боту.",
    "middleware.no_access_short": "⛔ Нет доступа",

    # ── Whoami ─────────────────────────────────────────────
    "whoami.anonymous": "Анонимный аккаунт",
    "whoami.info": (
        "🆔 <b>{id}</b> {full_name}\n"
        "📄 Резюме: {resumes_count}\n"
        "👁️ Новые просмотры: +{new_views}\n"
        "✉️ Непрочитанные: +{unread}"
    ),

    # ── Auth ────────────────────────────────────────────────
    "auth.login_prompt": (
        "👤 <b>Вход в аккаунт HH</b>\n\n"
        "Введите ваш email или номер телефона:"
    ),
    "auth.invalid_username": "❌ Введите корректный email или телефон.",
    "auth.login_confirm": (
        "📧 Логин: <code>{username}</code>\n\n"
        "Выберите способ входа:"
    ),
    "auth.starting": "⏳ Начинаю авторизацию...",
    "auth.password_prompt": (
        "🔒 Введите пароль от аккаунта HH:\n\n"
        "<i>Сообщение с паролем будет удалено после обработки.</i>"
    ),
    "auth.empty_password": "❌ Пароль не может быть пустым.",
    "auth.cancelled": "❌ Авторизация отменена.",
    "auth.already_authenticated": "✅ Вы авторизованы! Выберите действие:",
    "auth.session_ended": "Сессия авторизации завершена. Попробуйте /login",
    "auth.tokens_prompt": (
        "🔐 <b>Авторизация через токены</b>\n\n"
        "Отправьте токены в формате (каждый на новой строке):\n"
        "<code>access_token</code>\n"
        "<code>refresh_token</code>\n\n"
        "<b>Как получить:</b>\n"
        "1. <code>hh-applicant-tool auth</code>\n"
        "2. <code>hh-applicant-tool config</code>\n"
        "3. Скопируйте access_token и refresh_token"
    ),
    "auth.tokens_invalid_format": (
        "❌ Нужно 2 строки: access_token и refresh_token.\n"
        "Попробуйте ещё раз."
    ),
    "auth.tokens_invalid_prefix": "❌ access_token должен начинаться с 'USER'.",
    "auth.tokens_success": "✅ Авторизация успешна!\n\n{info}",
    "auth.tokens_failed": "❌ Не удалось авторизоваться: {error}",
    "auth.loading_profile": "⏳ Загрузка профиля...",
    "auth.not_logged_in": "Вы и так не авторизованы.",
    "auth.logout_confirm": "Вы уверены, что хотите выйти?",
    "auth.logged_out": "✅ Вы вышли из аккаунта.",
    "auth.already_in_progress": "⚠️ Авторизация уже запущена. Дождитесь завершения или /cancel.",
    "auth.captcha_prompt": "🔒 Требуется ввод капчи. Отправьте текст с картинки:",
    "auth.captcha_timeout": "Время ожидания капчи истекло.",
    "auth.playwright_missing": (
        "❌ Playwright не установлен.\n\n"
        "Используйте авторизацию через токены (/login_tokens)."
    ),
    "auth.opening_page": "⏳ Открываю страницу авторизации HH...",
    "auth.entering_password": "⏳ Вхожу с паролем...",
    "auth.code_form_timeout": (
        "❌ Не удалось дождаться формы ввода кода. "
        "Попробуйте снова или используйте вход с паролем."
    ),
    "auth.code_sent": (
        "📨 Код отправлен! Проверьте почту или SMS.\n\n"
        "📩 <b>Отправьте полученный код сюда:</b>"
    ),
    "auth.code_timeout": "❌ Время ожидания кода истекло.",
    "auth.waiting_confirmation": "⏳ Ожидаю подтверждение...",
    "auth.no_auth_code": "❌ Не удалось получить код авторизации от HH.",
    "auth.success_with_info": "🔓 Авторизация прошла успешно!\n\n{info}",
    "auth.success": "🔓 Авторизация прошла успешно!",
    "auth.timeout": "❌ Время ожидания истекло. Попробуйте снова.",
    "auth.error": "❌ Ошибка авторизации: {error}",

    # ── Resumes ────────────────────────────────────────────
    "resumes.empty": "У вас нет резюме.",
    "resumes.header": "📄 <b>Ваши резюме:</b>\n",
    "resumes.item": (
        "{icon} <b>{title}</b>\n"
        "   Статус: {status}\n"
        "   ID: <code>{id}</code>"
    ),
    "resumes.no_updates": "⏸ Нет резюме, доступных для обновления.",
    "resumes.updated_section": "Обновлены:\n{titles}",
    "resumes.updated_item": "  ✅ {title}",
    "resumes.error_section": "Ошибки:\n{errors}",
    "resumes.error_item": "  ❌ {error}",
    "resumes.loading": "⏳ Загрузка резюме...",
    "resumes.updating": "⏳ Обновляю резюме...",

    # ── Token ──────────────────────────────────────────────
    "token.refreshed": "✅ Токен успешно обновлён.",
    "token.not_expired": "ℹ️ Токен ещё не истёк, обновление не требуется.",
    "token.checking": "⏳ Проверяю токен...",
    "token.refresh_error": "❌ Ошибка обновления токена: {error}",

    # ── Apply ──────────────────────────────────────────────
    "apply.no_published": "⚠️ У вас нет опубликованных резюме.",
    "apply.resume_start": "🚀 Рассылаю отклики с резюме: <b>{title}</b>",
    "apply.vacancies_error": "❌ Ошибка загрузки вакансий: {error}",
    "apply.progress": "📨 Отправлено откликов: {count}...",
    "apply.limit_reached": "⚠️ Достигнут лимит откликов на сегодня.",
    "apply.done": (
        "📝 <b>Рассылка завершена!</b>\n"
        "✅ Отправлено: {applied}\n"
        "⏭ Пропущено: {skipped}"
    ),
    "apply.start_prompt": (
        "🚀 <b>Рассылка откликов</b>\n\n"
        "Утилита откликнется на все подходящие вакансии "
        "со всех опубликованных резюме.\n\n"
        "Выберите режим:"
    ),
    "apply.search_prompt": (
        "🔍 Введите поисковый запрос для вакансий.\n\n"
        "Примеры:\n"
        "• <code>Python backend</code>\n"
        "• <code>(Go OR Golang) NOT PHP</code>\n"
        "• <code>DevOps инженер</code>\n\n"
        "Отправьте <code>-</code> чтобы пропустить."
    ),
    "apply.excluded_prompt": (
        "🚫 Укажите исключаемые слова через запятую.\n\n"
        "Вакансии, содержащие эти слова в названии или описании, "
        "будут пропущены.\n\n"
        "Пример: <code>fullstack, junior, php, bitrix</code>\n\n"
        "Отправьте <code>-</code> чтобы пропустить."
    ),
    "apply.message_prompt": (
        "✉️ Введите шаблон сопроводительного письма (необязательно).\n\n"
        "Доступные плейсхолдеры:\n"
        "<code>%(vacancy_name)s</code> — название вакансии\n"
        "<code>%(employer_name)s</code> — работодатель\n"
        "<code>%(first_name)s</code> — ваше имя\n"
        "<code>%(last_name)s</code> — фамилия\n"
        "<code>%(resume_title)s</code> — название резюме\n\n"
        "Рандомизация: <code>{Привет|Здравствуйте}</code>\n\n"
        "Отправьте <code>-</code> чтобы пропустить."
    ),
    "apply.running": (
        "🚀 Рассылка откликов запущена...\n"
        "Это может занять несколько минут."
    ),
    "apply.error": "❌ Ошибка при рассылке: {error}",

    # ── Negotiations ───────────────────────────────────────
    "negotiations.empty": "У вас нет активных откликов.",
    "negotiations.header": "📊 <b>Ваши отклики</b> (всего: {count})\n",
    "negotiations.cleared": "✅ Удалено откликов: {count}",
    "negotiations.loading": "⏳ Загрузка откликов...",
    "negotiations.clear_prompt": (
        "🗑️ <b>Очистка откликов</b>\n\n"
        "Выберите, что удалить:"
    ),
    "negotiations.clearing_discards": "🗑️ Удаляю отказы...",
    "negotiations.days_prompt": (
        "📅 Введите количество дней.\n"
        "Будут удалены отклики, не обновлявшиеся дольше указанного срока."
    ),
    "negotiations.clearing_older": "🗑️ Удаляю отклики старше {days} дней...",
    "negotiations.reply_prompt": (
        "💬 <b>Ответ работодателям</b>\n\n"
        "Бот отправит сообщение во все чаты, "
        "где есть непрочитанный ответ работодателя.\n\n"
        "Введите шаблон сообщения:\n\n"
        "Плейсхолдеры:\n"
        "<code>%(vacancy_name)s</code> — вакансия\n"
        "<code>%(employer_name)s</code> — работодатель\n"
        "<code>%(first_name)s</code> — ваше имя\n\n"
        "Пример:\n"
        "<code>Здравствуйте! Спасибо за ответ по вакансии "
        "%(vacancy_name)s. Готов обсудить детали.</code>"
    ),
    "negotiations.replying": "💬 Рассылаю ответы...",

    # ── Reply ──────────────────────────────────────────────
    "reply.done": "📝 Отправлено ответов: {count}",

    # ── API ────────────────────────────────────────────────
    "api.usage": (
        "Использование: <code>/api /endpoint [key=value ...]</code>\n\n"
        "Примеры:\n"
        "<code>/api /me</code>\n"
        "<code>/api /employers text=IT</code>"
    ),
    "api.loading": "⏳ Запрос к API...",

    # ── Start / Help ───────────────────────────────────────
    "start.welcome_back": "👋 С возвращением! Выберите действие:",
    "start.welcome": (
        "👋 Добро пожаловать в <b>HH Bot</b>!\n\n"
        "Этот бот поможет автоматизировать поиск работы на hh.ru:\n"
        "• Массовая рассылка откликов\n"
        "• Обновление резюме\n"
        "• Ответы работодателям\n"
        "• Управление откликами\n\n"
        "Для начала необходимо авторизоваться."
    ),
    "start.help": (
        "<b>📖 Справка по командам</b>\n\n"
        "<b>Основные:</b>\n"
        "/start — Главное меню\n"
        "/whoami — Информация о профиле\n"
        "/resumes — Список резюме\n"
        "/update — Обновить все резюме\n\n"
        "<b>Отклики:</b>\n"
        "/apply — Рассылка откликов\n"
        "/negotiations — Статистика откликов\n"
        "/clear — Очистка откликов\n"
        "/reply — Ответ работодателям\n\n"
        "<b>Прочее:</b>\n"
        "/refresh — Обновить токен доступа\n"
        "/logout — Выйти из аккаунта\n"
        "/api — Вызов метода HH API\n\n"
        "<b>Шаблоны сообщений</b>\n"
        "Плейсхолдеры: <code>%(vacancy_name)s</code>, "
        "<code>%(employer_name)s</code>, <code>%(first_name)s</code>, "
        "<code>%(last_name)s</code>, <code>%(resume_title)s</code>\n"
        "Варианты: <code>{Привет|Здравствуйте}</code>"
    ),
    "start.cancelled": "❌ Действие отменено.",
}


def t(key: str, **kwargs: object) -> str:
    """Возвращает отформатированный текстовый шаблон по ключу."""
    template = TEXTS[key]
    return template.format(**kwargs) if kwargs else template
