# HH Bot — Telegram-бот для автоматизации hh.ru

Telegram-бот, предоставляющий функционал [hh-applicant-tool](https://github.com/s3rgeym/hh-applicant-tool) через удобный интерфейс в Telegram.

## Возможности

- **Авторизация** — вход через токены или OAuth
- **Рассылка откликов** — массовые отклики на подходящие вакансии с фильтрами
- **Управление резюме** — просмотр и обновление всех резюме
- **Ответы работодателям** — автоматическая рассылка ответов в чаты
- **Очистка откликов** — удаление отказов и устаревших откликов
- **Статистика** — просмотр статуса откликов
- **Обновление токена** — автоматическое продление доступа
- **Вызов API** — произвольные запросы к HH API

## Быстрый старт

### 1. Создайте Telegram-бота

Получите токен у [@BotFather](https://t.me/BotFather).

### 2. Настройте окружение

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
BOT_TOKEN=123456:ABC-DEF...
ALLOWED_USERS=123456789    # ваш Telegram ID (необязательно)
DATA_DIR=./data
```

### 3. Запуск через Docker

```bash
docker compose up -d
```

Для Celery-контура в runtime обычно поднимаются `hh-bot` и `hh-bot-worker`.
`hh-bot-beat` включается отдельно только когда в проекте есть реальные periodic jobs.

### 3 (альтернатива). Локальный запуск

```bash
pip install ./hh-applicant-tool
pip install -r requirements.txt
python -m bot
```

## Post-restore процесс для `hh-applicant-tool`

После любых изменений или восстановления файлов в `hh-applicant-tool` обязательно:

```bash
pip install --force-reinstall ./hh-applicant-tool
python scripts/check_installed_backends.py
python scripts/import_smoke_storage.py
```

Что это гарантирует:
- установленный пакет в `site-packages` действительно обновлен;
- `hh_applicant_tool.backends` присутствует и импортируется не из source tree;
- runtime-импорты `bot.storage.filesystem` и `bot.storage.postgres` проходят без `PYTHONPATH`-маскировки.

Для формализованной регрессионной проверки stale/recovery сценария:

```bash
python scripts/stale_package_recovery_check.py
```

Скрипт выполняет controlled negative (`FAIL`) и recovery (`PASS`) и сохраняет лог evidence в `artifacts/stale-scenario/`.

## Политика включения `hh-bot-beat`

### Когда включать beat

- В коде есть хотя бы одна продуктовая periodic job (cron/interval), согласованная с владельцем.
- Для periodic jobs определена lock/singleton политика, исключающая дубли запусков.
- Назначен owner расписаний и подтвержден путь эскалации инцидентов.

### Когда beat не включать

- Все heavy-операции запускаются только по действию пользователя.
- В коде отсутствуют periodic jobs.
- Нет согласованного owner/runbook для сопровождения расписаний.

### Lock/singleton policy для periodic jobs

- Каждая periodic job должна иметь уникальный lock-ключ.
- Повторный запуск блокируется, если предыдущий инстанс задачи еще активен.
- Для lock рекомендуется Redis (`SET NX EX`) с TTL больше ожидаемой длительности задачи.
- При ошибке lock задача должна завершаться безопасно без выполнения бизнес-логики.

### Owner и эскалация

- Owner по умолчанию: `backend on-call`.
- Первичная эскалация: владелец релиза/дежурный backend on-call.
- Вторичная эскалация: platform/ops (если проблема в инфраструктуре broker/worker/beat).

## Авторизация в боте

### Основной способ: Прямой вход через бота

1. Нажмите **«Войти в HH»**
2. Введите email или телефон
3. Выберите способ: **по коду** (придёт на почту/SMS) или **по паролю**
4. Если появится капча — бот пришлёт картинку, введите текст
5. Введите полученный код — готово!

Бот запускает headless-браузер (Playwright) на сервере и выполняет авторизацию за вас. Пароль удаляется из чата сразу после обработки.

### Резервный способ: Через токены

1. Установите `hh-applicant-tool` на любом устройстве
2. Выполните: `hh-applicant-tool auth`
3. Скопируйте токены: `hh-applicant-tool config`
4. В боте: `/login_tokens` и отправьте `access_token` + `refresh_token`

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/help` | Справка |
| `/whoami` | Информация о профиле |
| `/resumes` | Список резюме |
| `/update` | Обновить все резюме |
| `/apply` | Рассылка откликов |
| `/negotiations` | Статистика откликов |
| `/clear` | Очистить отклики |
| `/reply` | Ответить работодателям |
| `/refresh` | Обновить токен |
| `/logout` | Выйти из аккаунта |
| `/api` | Вызов метода HH API |

## Структура проекта

```
hh-bot/
├── bot/
│   ├── __main__.py         # Точка входа
│   ├── config.py           # Конфигурация
│   ├── hh_service.py       # Сервисный слой (обёртка над hh-applicant-tool)
│   ├── keyboards.py        # Клавиатуры Telegram
│   ├── states.py           # FSM-состояния
│   └── handlers/
│       ├── start.py        # /start, /help, отмена
│       ├── auth.py         # Авторизация, /whoami, /logout
│       ├── resumes.py      # Резюме
│       ├── apply.py        # Рассылка откликов
│       └── negotiations.py # Отклики, ответы, очистка
├── hh-applicant-tool/      # Git-субмодуль
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```
