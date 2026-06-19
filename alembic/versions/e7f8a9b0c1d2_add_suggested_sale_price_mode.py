"""add_suggested_sale_price_mode

Revision ID: e7f8a9b0c1d2
Revises: e2f3a4b5c6d7
Create Date: 2026-06-17

warehouse_items:
  + suggested_sale_price_mode VARCHAR(5) NOT NULL DEFAULT 'net'
  CHECK (suggested_sale_price_mode IN ('net', 'gross'))

warehouse_document_items:
  + suggested_sale_price_mode VARCHAR(5) NULL — snapshot z PZ (gross dla nowych normatywnych cen)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouse_items",
        sa.Column(
            "suggested_sale_price_mode",
            sa.String(5),
            nullable=False,
            server_default="net",
        ),
    )
    op.create_check_constraint(
        "ck_warehouse_items_suggested_sale_price_mode",
        "warehouse_items",
        "suggested_sale_price_mode IN ('net', 'gross')",
    )

    op.add_column(
        "warehouse_document_items",
        sa.Column("suggested_sale_price_mode", sa.String(5), nullable=True),
    )
    op.create_check_constraint(
        "ck_warehouse_document_items_suggested_sale_price_mode",
        "warehouse_document_items",
        "suggested_sale_price_mode IS NULL OR suggested_sale_price_mode IN ('net', 'gross')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_warehouse_document_items_suggested_sale_price_mode",
        "warehouse_document_items",
        type_="check",
    )
    op.drop_column("warehouse_document_items", "suggested_sale_price_mode")
    op.drop_constraint(
        "ck_warehouse_items_suggested_sale_price_mode",
        "warehouse_items",
        type_="check",
    )
    op.drop_column("warehouse_items", "suggested_sale_price_mode")
