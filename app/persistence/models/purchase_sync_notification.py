import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class PurchaseSyncNotificationORM(Base):
    """Kolejka e-maili podsumowujących sesję synchronizacji zakupów KSeF."""

    __tablename__ = "purchase_sync_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING", index=True)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="SUCCESS")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_invoice_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    invoice_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gross_sum: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    skipped_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recipient_email: Mapped[str] = mapped_column(String(1024), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_purchase_sync_notifications_status_sent", "status", "notification_sent_at"),
        Index("ix_purchase_sync_notifications_next_attempt", "status", "next_attempt_at"),
    )
