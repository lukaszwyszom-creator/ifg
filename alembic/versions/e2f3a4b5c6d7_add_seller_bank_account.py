"""add seller_bank_account to app_settings

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("seller_bank_account", sa.String(26), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "seller_bank_account")
