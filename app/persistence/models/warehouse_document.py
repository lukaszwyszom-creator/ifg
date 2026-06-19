from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.base import Base


class WarehouseDocumentNumberSeqORM(Base):
    """Licznik numerów dokumentów magazynowych per (doc_type, year).

    Inkrementowany atomowo przy księgowaniu (post_document) — odporny na równoległość.
    """
    __tablename__ = "warehouse_document_number_seq"

    doc_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class WarehouseDocumentORM(Base):
    __tablename__ = "warehouse_documents"
    __table_args__ = (
        Index(
            "uq_warehouse_documents_number",
            "number",
            unique=True,
            postgresql_where=text("number IS NOT NULL"),
        ),
        CheckConstraint(
            "status != 'posted' OR number IS NOT NULL",
            name="ck_warehouse_documents_posted_has_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # number nullable — gotowe pod przyszłą numerację PZ/0001/05/2026 bez migracji
    number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)   # WarehouseDocumentType
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)  # WarehouseDocumentStatus
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fiscal_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fiscal_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # correction_reason — wymagane dla KK (korekty stanu)
    correction_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # issue_reason — wymagane dla WZ bez faktury (podarunek, gratis, próbka, promocja itp.)
    issue_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # TODO POSTED documents are immutable and must not be edited by future update endpoints.
    #      Any PUT/PATCH on a POSTED document must check status and raise InvalidWarehouseDocumentError.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doc_items = relationship(
        "WarehouseDocumentItemORM",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class WarehouseDocumentItemORM(Base):
    __tablename__ = "warehouse_document_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouse_documents.id", ondelete="CASCADE"),
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
    # purchase_unit_price — cena zakupu (wymagana dla PZ i dodatniej KK); snapshot historyczny
    purchase_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    # unit_price_net — cena sprzedaży snapshot (opcjonalnie dla WZ z FV)
    unit_price_net: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # suggested_sale_price — sugerowana cena sprzedaży podana przy PZ; przy post() zapisywana na towarze
    suggested_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    suggested_sale_price_mode: Mapped[str | None] = mapped_column(String(5), nullable=True)

    document = relationship("WarehouseDocumentORM", back_populates="doc_items")
    item = relationship("WarehouseItemORM")


class WarehouseBalanceORM(Base):
    __tablename__ = "warehouse_balance"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouse_items.id"),
        primary_key=True,
    )
    # quantity_available — READ MODEL / cache dla UI.
    # ŹRÓDŁEM PRAWDY jest suma inventory_layers.remaining_quantity.
    # TODO: zaimplementować recalculate_balance(item_id) odbudowujące saldo z inventory_layers.
    # TODO: dodać walidację spójności: balance.quantity_available == SUM(remaining_quantity) per item.
    quantity_available: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    item = relationship("WarehouseItemORM")
