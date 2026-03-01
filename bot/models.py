"""ORM-модели SQLAlchemy для хранения данных пользователей."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""

    pass


class UserConfig(Base):
    """Конфигурация пользователя (токены, настройки)."""

    __tablename__ = "user_config"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    config_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    enc_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserCookies(Base):
    """Cookies пользователя в формате Netscape."""

    __tablename__ = "user_cookies"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cookies_text: Mapped[str] = mapped_column(Text, nullable=False)
    enc_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
