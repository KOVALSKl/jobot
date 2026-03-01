# Security And Key Rotation

## Runtime Secrets

Проект использует Docker secrets для runtime-конфигурации:

- `postgres_password`
- `bot_token`
- `encryption_key`
- опционально `encryption_keys_old` (список старых ключей через запятую)

Секреты должны существовать на сервере в директории `./secrets` рядом с `docker-compose.yml`
с правами:

- директория: `700`
- файлы: `600`

## Что шифруется

В PostgreSQL шифруются:

- токены в `user_config.config_data` (через JSON-обёртку с `ciphertext`)
- cookies в `user_cookies.cookies_text`

Поле `enc_version` хранит версию формата шифрования.

## Ротация ключей

Ротация выполняется в 3 шага:

1. Добавить новый ключ как `encryption_key` и старый ключ поместить в `encryption_keys_old`.
2. Запустить перешифрование данных (скрипт миграции/maintenance task): прочитать запись, расшифровать (новым/старым ключом), зашифровать новым.
3. После перешифрования всех записей удалить старые ключи из `encryption_keys_old`.

## Минимальные требования к ключу Fernet

Ключ `encryption_key` должен быть валидным ключом Fernet (base64 urlsafe, 32 байта).
Пример генерации:

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

