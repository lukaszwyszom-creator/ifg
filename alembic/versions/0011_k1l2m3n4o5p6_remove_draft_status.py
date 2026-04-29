"""remove_draft_status

Migracja statusu faktur: DRAFT -> READY_FOR_SUBMISSION.

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-26 22:10:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize all legacy draft statuses to ready_for_submission.
    op.execute(
        """
        UPDATE invoices
        SET status = 'ready_for_submission'
        WHERE lower(status) = 'draft';
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Unsafe downgrade: status 'draft' został usunięty z domeny i nie może być bezpiecznie odtworzony."
    )
