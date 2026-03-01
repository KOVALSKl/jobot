from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from bot.security.secrets import require_secret

load_dotenv()


def _parse_allowed_users() -> list[int]:
    raw = os.getenv("ALLOWED_USERS", "")
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


@dataclass
class Config:
    bot_token: str = field(
        default_factory=lambda: require_secret("bot_token", env_name="BOT_TOKEN")
    )
    allowed_users: list[int] = field(default_factory=_parse_allowed_users)

    def __post_init__(self) -> None:
        if not self.bot_token:
            raise ValueError("BOT_TOKEN не задан в переменных окружения")

    def is_user_allowed(self, user_id: int) -> bool:
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users


config = Config()
