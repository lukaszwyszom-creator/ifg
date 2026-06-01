"""warehouse_document_number_seq

Revision ID: d1e2f3a4b5c6
Revises: c8d1e2f3a4b5
Create Date: 2026-05-22 21:00:00.000000

Atomowa numeracja dokumentów magazynowych:
  - tabela warehouse_document_number_seq (doc_type, year, last_number)
  - unikalny indeks częściowy na warehouse_documents.number
  - constraint: POSTED wymaga number IS NOT NULL
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c8d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warehouse_document_number_seq",
        sa.Column("doc_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("doc_type", "year"),
    )

    # Zainicjuj liczniki z istniejących zaksięgowanych dokumentów (upgrade produkcyjny).
    op.execute(
        sa.text(
            """
            INSERT INTO warehouse_document_number_seq (doc_type, year, last_number)
            SELECT
                split_part(number, '/', 1),
                CAST(split_part(number, '/', 2) AS INTEGER),
                MAX(CAST(split_part(number, '/', 3) AS INTEGER))
            FROM warehouse_documents
            WHERE number IS NOT NULL
              AND number ~ '^[^/]+/[0-9]{4}/[0-9]+$'
            GROUP BY split_part(number, '/', 1), split_part(number, '/', 2)
            ON CONFLICT (doc_type, year) DO NOTHING
            """
        )
    )

    op.create_index(
        "uq_warehouse_documents_number",
        "warehouse_documents",
        ["number"],
        unique=True,
        postgresql_where=sa.text("number IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_warehouse_documents_posted_has_number",
        "warehouse_documents",
        "status != 'posted' OR number IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_warehouse_documents_posted_has_number",
        "warehouse_documents",
        type_="check",
    )
    op.drop_index(
        "uq_warehouse_documents_number",
        table_name="warehouse_documents",
        postgresql_where=sa.text("number IS NOT NULL"),
    )
    op.drop_table("warehouse_document_number_seq")
