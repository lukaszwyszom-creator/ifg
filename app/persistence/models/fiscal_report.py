from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.base import Base


class FiscalReportORM(Base):
    __tablename__ = "fiscal_reports"
    __table_args__ = (
        UniqueConstraint("period_year", "period_month", name="uq_fiscal_report_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # number nullable — gotowe pod przyszłą numerację RF/05/2026 bez migracji
    number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="entered_for_distribution", index=True
    )  # FiscalReportStatus
    total_gross: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    distributed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report_items = relationship(
        "FiscalReportItemORM",
        back_populates="report",
        cascade="all, delete-orphan",
    )


class FiscalReportItemORM(Base):
    __tablename__ = "fiscal_report_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fiscal_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouse_items.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_net: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    report = relationship("FiscalReportORM", back_populates="report_items")
    item = relationship("WarehouseItemORM")
