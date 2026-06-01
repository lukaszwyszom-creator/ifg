"""invoice_payment_method

Dodanie kolumny payment_method (gotówka/przelew) do tabeli invoices.

Revision ID: c8d1e2f3a4b5
Revises: b4e8c2d1f6a9
Create Date: 2026-05-22 12:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8d1e2f3a4b5"
down_revision = "b4e8c2d1f6a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("payment_method", sa.String(length=16), nullable=False, server_default="transfer"),
    )


def downgrade() -> None:
    op.drop_column("invoices", "payment_method")
