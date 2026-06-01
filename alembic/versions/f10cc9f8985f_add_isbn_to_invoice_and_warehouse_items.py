"""add_isbn_to_invoice_and_warehouse_items

Revision ID: f10cc9f8985f
Revises: c563ae397cf9
Create Date: 2026-05-22 00:00:00.000000

Dodaje kolumnę isbn (VARCHAR 17, nullable) do:
  invoice_items      — snapshot ISBN na fakturze
  warehouse_items    — ISBN w kartotece pozycji magazynowych
"""

import sqlalchemy as sa
from alembic import op

revision = "f10cc9f8985f"
down_revision = "c563ae397cf9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoice_items", sa.Column("isbn", sa.String(17), nullable=True))
    op.add_column("warehouse_items", sa.Column("isbn", sa.String(17), nullable=True))
    op.create_index("ix_warehouse_items_isbn", "warehouse_items", ["isbn"])


def downgrade() -> None:
    op.drop_index("ix_warehouse_items_isbn", table_name="warehouse_items")
    op.drop_column("warehouse_items", "isbn")
    op.drop_column("invoice_items", "isbn")
