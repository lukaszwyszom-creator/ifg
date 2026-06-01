"""add_warehouse_v1_tables

Revision ID: c563ae397cf9
Revises: n4o5p6q7r8s9
Create Date: 2026-05-21 22:00:00.000000

Tworzy tabele modułu Magazyn v1:
  warehouse_items, warehouse_documents, warehouse_document_items,
  warehouse_balance, fiscal_reports, fiscal_report_items
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c563ae397cf9"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Kartoteka pozycji ─────────────────────────────────────────────────────
    op.create_table(
        "warehouse_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="23"),
        sa.Column("default_price_net", sa.Numeric(18, 2), nullable=True),
        sa.Column("unit", sa.String(32), nullable=False, server_default="szt."),
        sa.Column("is_warehouse_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("number", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_warehouse_items_number", "warehouse_items", ["number"])

    # ── Raporty fiskalne (przed warehouse_documents — FK) ─────────────────────
    op.create_table(
        "fiscal_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(64), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(64),
            nullable=False,
            server_default="entered_for_distribution",
        ),
        sa.Column("total_gross", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_vat", sa.Numeric(18, 2), nullable=False),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "entered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("distributed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("period_year", "period_month", name="uq_fiscal_report_period"),
    )
    op.create_index("ix_fiscal_reports_period_year", "fiscal_reports", ["period_year"])
    op.create_index("ix_fiscal_reports_period_month", "fiscal_reports", ["period_month"])
    op.create_index("ix_fiscal_reports_status", "fiscal_reports", ["status"])

    # ── Dokumenty magazynowe ──────────────────────────────────────────────────
    op.create_table(
        "warehouse_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(64), nullable=True),
        sa.Column("doc_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column(
            "source_invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "fiscal_report_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fiscal_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_warehouse_documents_number", "warehouse_documents", ["number"])
    op.create_index("ix_warehouse_documents_doc_type", "warehouse_documents", ["doc_type"])
    op.create_index("ix_warehouse_documents_status", "warehouse_documents", ["status"])
    op.create_index(
        "ix_warehouse_documents_source_invoice_id", "warehouse_documents", ["source_invoice_id"]
    )
    op.create_index(
        "ix_warehouse_documents_fiscal_report_id", "warehouse_documents", ["fiscal_report_id"]
    )
    op.create_index("ix_warehouse_documents_created_at", "warehouse_documents", ["created_at"])

    # ── Pozycje dokumentów ────────────────────────────────────────────────────
    op.create_table(
        "warehouse_document_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_items.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price_net", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
    )
    op.create_index(
        "ix_warehouse_document_items_document_id", "warehouse_document_items", ["document_id"]
    )
    op.create_index(
        "ix_warehouse_document_items_item_id", "warehouse_document_items", ["item_id"]
    )

    # ── Stany magazynowe ──────────────────────────────────────────────────────
    op.create_table(
        "warehouse_balance",
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_items.id"),
            primary_key=True,
        ),
        sa.Column("quantity_available", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── Pozycje raportów fiskalnych ────────────────────────────────────────────
    op.create_table(
        "fiscal_report_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fiscal_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouse_items.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price_net", sa.Numeric(18, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
    )
    op.create_index("ix_fiscal_report_items_report_id", "fiscal_report_items", ["report_id"])
    op.create_index("ix_fiscal_report_items_item_id", "fiscal_report_items", ["item_id"])


def downgrade() -> None:
    op.drop_table("fiscal_report_items")
    op.drop_table("warehouse_balance")
    op.drop_table("warehouse_document_items")
    op.drop_table("warehouse_documents")
    op.drop_table("fiscal_reports")
    op.drop_table("warehouse_items")
