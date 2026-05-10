"""ksef_sync_state

Dodanie tabeli ksef_sync_states do lokalnego śledzenia statusu
synchronizacji zakupów z KSeF (idle/running/success/error).

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-10 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ksef_sync_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="idle", nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ksef_sync_states_scope", "ksef_sync_states", ["scope"], unique=True)
    op.create_index("ix_ksef_sync_states_status", "ksef_sync_states", ["status"], unique=False)
    op.create_index(
        "ix_ksef_sync_states_scope_status",
        "ksef_sync_states",
        ["scope", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ksef_sync_states_scope_status", table_name="ksef_sync_states")
    op.drop_index("ix_ksef_sync_states_status", table_name="ksef_sync_states")
    op.drop_index("ix_ksef_sync_states_scope", table_name="ksef_sync_states")
    op.drop_table("ksef_sync_states")
