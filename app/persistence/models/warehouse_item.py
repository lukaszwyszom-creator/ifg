from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class WarehouseItemORM(Base):
    __tablename__ = "warehouse_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)  # WarehouseItemType
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    default_price_net: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # Cena sugerowana sprzedaży — domyślnie trafia na FV/WZ; zmiana nie wpływa na historię
    suggested_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # net = historyczne dane; gross = normatywna cena brutto z PZ (od cutover)
    suggested_sale_price_mode: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default="net"
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="szt.")
    is_warehouse_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    isbn: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    # number nullable — gotowe pod przyszłą numerację bez migracji
    number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
