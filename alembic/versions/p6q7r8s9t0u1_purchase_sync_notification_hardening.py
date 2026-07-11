"""purchase_sync_notification_hardening

Retry SMTP, snapshot sesji, wielu odbiorców (GWO-IFG-NOTIFY-0002).

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-07-11 12:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_sync_notifications",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "purchase_sync_notifications",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_sync_notifications",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_sync_notifications",
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
    )
    op.add_column(
        "purchase_sync_notifications",
        sa.Column("invoice_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "purchase_sync_notifications",
        sa.Column("gross_sum", sa.Numeric(18, 2), server_default="0", nullable=False),
    )
    op.alter_column(
        "purchase_sync_notifications",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.create_index(
        "ix_purchase_sync_notifications_next_attempt",
        "purchase_sync_notifications",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_sync_notifications_next_attempt", table_name="purchase_sync_notifications")
    op.drop_column("purchase_sync_notifications", "gross_sum")
    op.drop_column("purchase_sync_notifications", "invoice_count")
    op.drop_column("purchase_sync_notifications", "max_attempts")
    op.drop_column("purchase_sync_notifications", "last_attempt_at")
    op.drop_column("purchase_sync_notifications", "next_attempt_at")
    op.drop_column("purchase_sync_notifications", "attempt_count")
    op.alter_column(
        "purchase_sync_notifications",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
