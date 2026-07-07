"""ksef_monitor_transmissions_unified

Revision ID: a9b1c2d3e4f5
Revises: f8a9b0c1d2e3
Create Date: 2026-07-07 09:40:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9b1c2d3e4f5"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transmissions", sa.Column("severity", sa.String(length=16), nullable=True))
    op.add_column(
        "transmissions",
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("transmissions", sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("transmissions", sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.execute(
        """
        UPDATE transmissions
        SET operation_type = 'SALE_SEND'
        WHERE operation_type IS NULL
           OR operation_type = ''
           OR operation_type IN ('submit', 'invoice_submit');
        """
    )
    op.execute(
        """
        UPDATE transmissions
        SET severity = CASE
            WHEN status = 'success' THEN 'SUCCESS'
            WHEN status IN ('failed_permanent') THEN 'ERROR'
            WHEN status IN ('failed_retryable', 'failed_temporary', 'waiting_status') THEN 'WARNING'
            WHEN status IN ('queued', 'processing') THEN 'RUNNING'
            ELSE 'INFO'
        END
        WHERE severity IS NULL;
        """
    )
    op.execute(
        """
        UPDATE transmissions
        SET correlation_id = COALESCE(invoice_id, id)
        WHERE correlation_id IS NULL;
        """
    )

    op.alter_column("transmissions", "invoice_id", nullable=True)
    op.alter_column("transmissions", "idempotency_key", nullable=True)
    op.alter_column("transmissions", "severity", nullable=False)
    op.alter_column("transmissions", "correlation_id", nullable=False)

    op.create_index("ix_transmissions_correlation_id", "transmissions", ["correlation_id"], unique=False)
    op.create_index("ix_transmissions_job_id", "transmissions", ["job_id"], unique=False)
    op.create_index(
        "ix_transmissions_correlation_id_created_at",
        "transmissions",
        ["correlation_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_transmissions_severity", "transmissions", ["severity"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transmissions_severity", table_name="transmissions")
    op.drop_index("ix_transmissions_correlation_id_created_at", table_name="transmissions")
    op.drop_index("ix_transmissions_job_id", table_name="transmissions")
    op.drop_index("ix_transmissions_correlation_id", table_name="transmissions")

    op.alter_column("transmissions", "correlation_id", nullable=True)
    op.alter_column("transmissions", "severity", nullable=True)
    op.alter_column("transmissions", "idempotency_key", nullable=False)
    op.alter_column("transmissions", "invoice_id", nullable=False)

    op.drop_column("transmissions", "metadata_json")
    op.drop_column("transmissions", "job_id")
    op.drop_column("transmissions", "correlation_id")
    op.drop_column("transmissions", "severity")
