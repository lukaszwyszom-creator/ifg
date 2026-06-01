"""add_wz_issue_reason

Revision ID: 770c033eeb7f
Revises: cb43e5557073
Create Date: 2026-05-22 18:00:00.000000

Zmiany:
  warehouse_documents:
    + issue_reason VARCHAR(512) — wymagane dla WZ bez faktury (tryb B)
"""

import sqlalchemy as sa
from alembic import op

revision = "770c033eeb7f"
down_revision = "cb43e5557073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouse_documents",
        sa.Column("issue_reason", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("warehouse_documents", "issue_reason")
