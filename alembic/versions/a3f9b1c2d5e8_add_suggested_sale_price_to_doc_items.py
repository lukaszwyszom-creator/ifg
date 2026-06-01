"""add_suggested_sale_price_to_doc_items

Revision ID: a3f9b1c2d5e8
Revises: 770c033eeb7f
Create Date: 2026-05-22 19:00:00.000000

Zmiany:
  warehouse_document_items:
    + suggested_sale_price NUMERIC(18,2) — cena sugerowana z PZ; zapisywana na towarze przy post()
"""

import sqlalchemy as sa
from alembic import op

revision = "a3f9b1c2d5e8"
down_revision = "770c033eeb7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouse_document_items",
        sa.Column("suggested_sale_price", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("warehouse_document_items", "suggested_sale_price")
