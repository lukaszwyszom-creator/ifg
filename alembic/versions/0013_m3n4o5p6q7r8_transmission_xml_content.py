"""transmission_xml_content

Dodanie kolumny xml_content (bytea) do tabeli transmissions.
Przechowuje dokładny XML FA(3) wysłany do KSeF — wymagane do audytu
i debugowania odrzuceń bez możliwości ponownego wygenerowania.

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-04 12:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transmissions",
        sa.Column("xml_content", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transmissions", "xml_content")
