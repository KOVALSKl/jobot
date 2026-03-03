"""Добавляет таблицу user_tasks.

Revision ID: 002
Revises: 001
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_tasks",
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("progress", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "cancel_requested", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_user_tasks_user_id", "user_tasks", ["user_id"], unique=False)
    op.create_index(
        "ix_user_tasks_operation", "user_tasks", ["operation"], unique=False
    )
    op.create_index("ix_user_tasks_status", "user_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_tasks_status", table_name="user_tasks")
    op.drop_index("ix_user_tasks_operation", table_name="user_tasks")
    op.drop_index("ix_user_tasks_user_id", table_name="user_tasks")
    op.drop_table("user_tasks")
