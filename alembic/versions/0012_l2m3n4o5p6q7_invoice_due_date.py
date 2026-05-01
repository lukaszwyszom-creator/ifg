"""invoice_due_date

Dodanie kolumny due_date (termin płatności) do tabeli invoices.

- DATE, nullable
- brak defaultów
- brak backfill (overdue liczone dynamicznie po stronie aplikacji)

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-01 09:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l2m3n4o5p6q7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("due_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoices", "due_date")
