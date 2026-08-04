"""invoice_items.warehouse_item_id FK to warehouse_items

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-08-04 00:00:00.000000

Trwałe powiązanie pozycji faktury z kanoniczną kartoteką magazynową IFG.
Kolumna nullable — historyczne faktury pozostają z warehouse_item_id=NULL.
ON DELETE RESTRICT — nie wolno usunąć WarehouseItem użytego na fakturze.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoice_items",
        sa.Column("warehouse_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoice_items_warehouse_item_id",
        "invoice_items",
        "warehouse_items",
        ["warehouse_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_invoice_items_warehouse_item_id",
        "invoice_items",
        ["warehouse_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_items_warehouse_item_id", table_name="invoice_items")
    op.drop_constraint(
        "fk_invoice_items_warehouse_item_id",
        "invoice_items",
        type_="foreignkey",
    )
    op.drop_column("invoice_items", "warehouse_item_id")
