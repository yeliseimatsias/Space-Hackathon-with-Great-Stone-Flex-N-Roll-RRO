"""Initial schema with pgvector.

Revision ID: 001_initial
Revises:
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bitrix_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("max_dialogs", sa.Integer(), nullable=False),
        sa.Column("active_dialogs", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bitrix_user_id"),
    )
    op.create_index(
        "ix_employees_bitrix_user_id", "employees", ["bitrix_user_id"], unique=False
    )

    op.create_table(
        "knowledge_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("expert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expert_rating_at_time", sa.Float(), nullable=False),
        sa.Column("similarity_threshold", sa.Float(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["expert_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        CREATE INDEX knowledge_items_embedding_idx
        ON knowledge_items
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=100), nullable=False),
        sa.Column("bitrix_lead_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_employee_id"],
            ["employees.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_index(
        "ix_conversations_telegram_chat_id",
        "conversations",
        ["telegram_chat_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_telegram_chat_id", table_name="conversations")
    op.drop_table("conversations")
    op.execute("DROP INDEX IF EXISTS knowledge_items_embedding_idx;")
    op.drop_table("knowledge_items")
    op.drop_index("ix_employees_bitrix_user_id", table_name="employees")
    op.drop_table("employees")
    op.execute("DROP EXTENSION IF EXISTS vector;")
