"""Шифрование/дешифрование чувствительных данных приложения."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from bot.security.secrets import get_secret, require_secret


class CryptoService:
    """Сервис симметричного шифрования на базе Fernet."""

    ENC_VERSION = 1

    def __init__(self, primary_key: str, old_keys: list[str] | None = None) -> None:
        self._current = Fernet(primary_key.encode("utf-8"))
        self._fallbacks = [
            Fernet(k.encode("utf-8")) for k in (old_keys or []) if k.strip()
        ]

    def encrypt_text(self, plaintext: str) -> str:
        """Шифрует текст и возвращает base64-токен."""
        return self._current.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt_text(self, token: str) -> str:
        """Дешифрует токен текущим или одним из предыдущих ключей."""
        for cipher in [self._current, *self._fallbacks]:
            try:
                return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
            except InvalidToken:
                continue
        raise ValueError("Не удалось расшифровать данные: ключ не подходит.")

    def encrypt_json(self, data: dict[str, Any]) -> dict[str, Any]:
        """Шифрует словарь и возвращает JSON-обёртку с версией формата."""
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return {
            "enc_version": self.ENC_VERSION,
            "ciphertext": self.encrypt_text(payload),
        }

    def decrypt_json(self, encrypted_data: dict[str, Any]) -> dict[str, Any]:
        """Дешифрует JSON-обёртку с ciphertext."""
        token = encrypted_data.get("ciphertext")
        if not token:
            raise ValueError("Зашифрованные данные не содержат ciphertext.")
        raw = self.decrypt_text(str(token))
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("Дешифрованные данные имеют неверный формат.")
        return decoded


def get_crypto_service() -> CryptoService:
    """Создаёт CryptoService из runtime secrets/env."""
    primary = require_secret("encryption_key", env_name="ENCRYPTION_KEY")
    old_keys_raw = get_secret("encryption_keys_old", env_name="ENCRYPTION_KEYS_OLD")
    old_keys = [k.strip() for k in old_keys_raw.split(",") if k.strip()] if old_keys_raw else []
    return CryptoService(primary_key=primary, old_keys=old_keys)

