from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.persistence.models.purchase_sync_notification import PurchaseSyncNotificationORM
from app.services.purchase_sync_notify_config import retry_delay_seconds


class PurchaseSyncNotificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_correlation_id(self, correlation_id: UUID) -> PurchaseSyncNotificationORM | None:
        return self.session.execute(
            select(PurchaseSyncNotificationORM).where(
                PurchaseSyncNotificationORM.correlation_id == correlation_id
            )
        ).scalar_one_or_none()

    def add(self, row: PurchaseSyncNotificationORM) -> PurchaseSyncNotificationORM:
        self.session.add(row)
        self.session.flush()
        return row

    def claim_processable(self, *, limit: int = 5, now: datetime | None = None) -> list[PurchaseSyncNotificationORM]:
        """Atomowe przejęcie rekordów do wysyłki (FOR UPDATE SKIP LOCKED na PostgreSQL)."""
        current = now or datetime.now(UTC)
        stmt = (
            select(PurchaseSyncNotificationORM)
            .where(
                PurchaseSyncNotificationORM.notification_sent_at.is_(None),
                PurchaseSyncNotificationORM.status.in_(("PENDING", "FAILED")),
                or_(
                    PurchaseSyncNotificationORM.next_attempt_at.is_(None),
                    PurchaseSyncNotificationORM.next_attempt_at <= current,
                ),
            )
            .order_by(PurchaseSyncNotificationORM.created_at.asc())
            .limit(limit)
        )
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        else:
            stmt = stmt.with_for_update()
        return list(self.session.execute(stmt).scalars())

    def begin_attempt(self, row: PurchaseSyncNotificationORM, *, now: datetime | None = None) -> int:
        """Rejestruje rozpoczęcie próby wysyłki — zwraca numer próby (1-based)."""
        current = now or datetime.now(UTC)
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.last_attempt_at = current
        row.updated_at = current
        self.session.flush()
        return row.attempt_count

    def mark_sent(self, row: PurchaseSyncNotificationORM) -> None:
        now = datetime.now(UTC)
        row.status = "SENT"
        row.notification_sent_at = now
        row.last_error = None
        row.next_attempt_at = None
        row.updated_at = now

    def mark_retry_or_permanent(self, row: PurchaseSyncNotificationORM, error: str) -> str:
        """Po błędzie SMTP: FAILED + next_attempt_at albo FAILED_PERMANENT."""
        now = datetime.now(UTC)
        row.last_error = error[:1024]
        row.updated_at = now
        max_attempts = int(row.max_attempts or 5)
        if row.attempt_count >= max_attempts:
            row.status = "FAILED_PERMANENT"
            row.next_attempt_at = None
            return "FAILED_PERMANENT"

        row.status = "FAILED"
        delay = retry_delay_seconds(row.attempt_count)
        row.next_attempt_at = now + timedelta(seconds=delay) if delay > 0 else now
        return "FAILED"

    def mark_failed(self, row: PurchaseSyncNotificationORM, error: str) -> None:
        """Kompatybilność wsteczna — deleguje do mark_retry_or_permanent."""
        self.mark_retry_or_permanent(row, error)
