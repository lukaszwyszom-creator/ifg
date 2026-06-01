"""Warstwy magazynowe FIFO.

Każde zaksięgowane PZ (i dodatnia KK) tworzy warstwę.
WZ i ujemna KK schodzą z warstw w kolejności FIFO (najstarsza pierwsza).
InventoryLayerMovement rejestruje, z której warstwy i ile zdjęto — umożliwia
pełne odtworzenie kosztu własnego sprzedaży.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.base import Base


class InventoryLayerORM(Base):
    __tablename__ = "inventory_layers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouse_items.id"),
        nullable=False,
        index=True,
    )
    # powiązanie z pozycją dokumentu źródłowego (PZ lub KK)
    source_document_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouse_document_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_document_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "PZ" | "KK"
    # received_quantity — pierwotna ilość przyjęta (niezmienna)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # remaining_quantity — ile jeszcze dostępne; maleje przy WZ/ujemnej KK
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # purchase_unit_price — cena zakupu; NIEZMIENNA po zaksięgowaniu
    purchase_unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    item = relationship("WarehouseItemORM")
    movements = relationship(
        "InventoryLayerMovementORM",
        back_populates="layer",
        cascade="all, delete-orphan",
    )


class InventoryLayerMovementORM(Base):
    """Rejestruje z której warstwy i ile zdjął konkretny WZ lub ujemna KK.

    Umożliwia odtworzenie kosztu własnego sprzedaży dla każdego wydania.
    """
    __tablename__ = "inventory_layer_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_layers.id"),
        nullable=False,
        index=True,
    )
    warehouse_document_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouse_document_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity_consumed: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # snapshot ceny zakupu z warstwy w momencie wydania — immutable
    purchase_unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    layer = relationship("InventoryLayerORM", back_populates="movements")
