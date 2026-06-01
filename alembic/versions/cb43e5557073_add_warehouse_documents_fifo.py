"""add_warehouse_documents_fifo

Revision ID: cb43e5557073
Revises: f10cc9f8985f
Create Date: 2026-05-22 17:00:00.000000

Zmiany:
  warehouse_items:
    + suggested_sale_price NUMERIC(18,2)
  warehouse_documents:
    + correction_reason VARCHAR(512)
    + posted_at TIMESTAMPTZ
    - confirmed_at (usunięte — nie użyte)
  warehouse_document_items:
    + purchase_unit_price NUMERIC(18,4)
    ~ unit_price_net / vat_rate → nullable
  NOWE TABELE:
    inventory_layers
    inventory_layer_movements
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "cb43e5557073"
down_revision = "f10cc9f8985f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── warehouse_items ───────────────────────────────────────────────────────
    op.add_column(
        "warehouse_items",
        sa.Column("suggested_sale_price", sa.Numeric(18, 2), nullable=True),
    )

    # ── warehouse_documents ───────────────────────────────────────────────────
    op.add_column(
        "warehouse_documents",
        sa.Column("correction_reason", sa.String(512), nullable=True),
    )
    op.add_column(
        "warehouse_documents",
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # confirmed_at → zastąpione przez posted_at; zachowujemy kolumnę jako nullable dla kompatybilności
    # (nie usuwamy żeby nie tracić historii jeśli była używana)

    # ── warehouse_document_items ──────────────────────────────────────────────
    op.add_column(
        "warehouse_document_items",
        sa.Column("purchase_unit_price", sa.Numeric(18, 4), nullable=True),
    )
    # unit_price_net i vat_rate → nullable (PZ nie wymaga cen sprzedaży)
    op.alter_column("warehouse_document_items", "unit_price_net", nullable=True)
    op.alter_column("warehouse_document_items", "vat_rate", nullable=True)

    # ── inventory_layers ──────────────────────────────────────────────────────
    op.create_table(
        "inventory_layers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_items.id"),
            nullable=False,
        ),
        sa.Column(
            "source_document_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_document_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_document_type", sa.String(16), nullable=False),
        sa.Column("received_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("purchase_unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("is_correction", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_inventory_layers_item_id", "inventory_layers", ["item_id"])
    op.create_index("ix_inventory_layers_received_date", "inventory_layers", ["received_date"])
    op.create_index(
        "ix_inventory_layers_source_document_item_id",
        "inventory_layers",
        ["source_document_item_id"],
    )

    # ── inventory_layer_movements ─────────────────────────────────────────────
    op.create_table(
        "inventory_layer_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "layer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inventory_layers.id"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_document_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_document_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity_consumed", sa.Numeric(18, 4), nullable=False),
        sa.Column("purchase_unit_price_snapshot", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_inventory_layer_movements_layer_id", "inventory_layer_movements", ["layer_id"]
    )
    op.create_index(
        "ix_inventory_layer_movements_doc_item_id",
        "inventory_layer_movements",
        ["warehouse_document_item_id"],
    )


def downgrade() -> None:
    op.drop_table("inventory_layer_movements")
    op.drop_table("inventory_layers")
    op.drop_column("warehouse_document_items", "purchase_unit_price")
    op.alter_column("warehouse_document_items", "unit_price_net", nullable=False)
    op.alter_column("warehouse_document_items", "vat_rate", nullable=False)
    op.drop_column("warehouse_documents", "posted_at")
    op.drop_column("warehouse_documents", "correction_reason")
    op.drop_column("warehouse_items", "suggested_sale_price")
