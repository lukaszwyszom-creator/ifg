"""PZ draft: nullable layer cost, nullable movement snapshot, unique source doc item.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-19

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "inventory_layers",
        "purchase_unit_price",
        existing_type=sa.Numeric(18, 4),
        nullable=True,
    )
    op.alter_column(
        "inventory_layer_movements",
        "purchase_unit_price_snapshot",
        existing_type=sa.Numeric(18, 4),
        nullable=True,
    )
    op.create_index(
        "uq_inventory_layers_source_doc_item",
        "inventory_layers",
        ["source_document_item_id"],
        unique=True,
        postgresql_where=sa.text("source_document_item_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_inventory_layers_source_doc_item",
        table_name="inventory_layers",
        postgresql_where=sa.text("source_document_item_id IS NOT NULL"),
    )
    op.alter_column(
        "inventory_layer_movements",
        "purchase_unit_price_snapshot",
        existing_type=sa.Numeric(18, 4),
        nullable=False,
    )
    op.alter_column(
        "inventory_layers",
        "purchase_unit_price",
        existing_type=sa.Numeric(18, 4),
        nullable=False,
    )
