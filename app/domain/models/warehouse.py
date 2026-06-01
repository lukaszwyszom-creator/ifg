"""Modele domenowe dokumentów magazynowych (czyste dataclasses, bez SQLAlchemy)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums import WarehouseDocumentStatus, WarehouseDocumentType


@dataclass(slots=True)
class WarehouseDocItem:
    item_id: UUID
    quantity: Decimal
    # purchase_unit_price — wymagane dla PZ i dodatniej KK (FIFO pricing)
    purchase_unit_price: Decimal | None = None
    # unit_price_net — opcjonalny snapshot ceny sprzedaży z FV (dla WZ)
    unit_price_net: Decimal | None = None
    vat_rate: Decimal | None = None
    id: UUID | None = None


@dataclass(slots=True)
class WarehouseDoc:
    id: UUID
    doc_type: WarehouseDocumentType
    status: WarehouseDocumentStatus
    items: list[WarehouseDocItem] = field(default_factory=list)
    number: str | None = None
    correction_reason: str | None = None
    source_invoice_id: UUID | None = None
    fiscal_report_id: UUID | None = None
    notes: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    posted_at: datetime | None = None
