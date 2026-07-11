"""purchase_sync_notification_queue

Kolejka e-maili podsumowujących sesję synchronizacji zakupów KSeF.

Revision ID: o5p6q7r8s9t0
Revises: a9b1c2d3e4f5
Create Date: 2026-07-11 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "o5p6q7r8s9t0"
down_revision = "a9b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_sync_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("sync_status", sa.String(length=32), server_default="SUCCESS", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "new_invoice_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("skipped_duplicates", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recipient_email", sa.String(length=256), nullable=False),
        sa.Column("notification_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correlation_id"),
    )
    op.create_index(
        "ix_purchase_sync_notifications_correlation_id",
        "purchase_sync_notifications",
        ["correlation_id"],
        unique=True,
    )
    op.create_index(
        "ix_purchase_sync_notifications_status",
        "purchase_sync_notifications",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_purchase_sync_notifications_status_sent",
        "purchase_sync_notifications",
        ["status", "notification_sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_sync_notifications_status_sent", table_name="purchase_sync_notifications")
    op.drop_index("ix_purchase_sync_notifications_status", table_name="purchase_sync_notifications")
    op.drop_index("ix_purchase_sync_notifications_correlation_id", table_name="purchase_sync_notifications")
    op.drop_table("purchase_sync_notifications")
