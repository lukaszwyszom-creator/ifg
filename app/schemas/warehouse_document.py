from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.enums import WarehouseDocumentType

_SALE_PRICE_MODES = frozenset({"net", "gross"})


class WarehouseDocItemInput(BaseModel):
    item_id: UUID
    quantity: Decimal
    purchase_unit_price: Decimal | None = None
    unit_price_net: Decimal | None = None
    vat_rate: Decimal | None = None
    # suggested_sale_price — podawane przy PZ; na post() zapisywane na towarze
    suggested_sale_price: Decimal | None = None
    suggested_sale_price_mode: str | None = None

    @field_validator("suggested_sale_price_mode")
    @classmethod
    def validate_suggested_sale_price_mode(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in _SALE_PRICE_MODES:
            raise ValueError("suggested_sale_price_mode musi być 'net' lub 'gross'.")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_nonzero_integer(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("Ilość pozycji nie może być zerem.")
        if v != v.to_integral_value():
            raise ValueError("Ilość pozycji musi być liczbą całkowitą.")
        return v


class WarehouseDocCreateRequest(BaseModel):
    doc_type: WarehouseDocumentType
    items: list[WarehouseDocItemInput]
    notes: str | None = None
    correction_reason: str | None = None
    # issue_reason — wymagane dla WZ bez faktury (tryb B: podarunek, gratis, próbka itp.)
    issue_reason: str | None = None
    source_invoice_id: UUID | None = None
    fiscal_report_id: UUID | None = None


class WarehouseDocFifoMovementResponse(BaseModel):
    source_document_number: str | None
    source_document_date: date | None
    quantity_consumed: Decimal
    unit_price_net: Decimal


class WarehouseDocItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    quantity: Decimal
    purchase_unit_price: Decimal | None
    unit_price_net: Decimal | None
    vat_rate: Decimal | None
    suggested_sale_price: Decimal | None
    suggested_sale_price_mode: str | None
    fifo_movements: list[WarehouseDocFifoMovementResponse] = []


class WarehouseDocResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str | None
    doc_type: str
    status: str
    notes: str | None
    correction_reason: str | None
    issue_reason: str | None
    source_invoice_id: UUID | None
    fiscal_report_id: UUID | None
    created_at: datetime
    posted_at: datetime | None
    items: list[WarehouseDocItemResponse] = []

    @classmethod
    def from_orm(
        cls,
        doc: object,
        fifo_by_item_id: dict[UUID, list[WarehouseDocFifoMovementResponse]] | None = None,
    ) -> "WarehouseDocResponse":
        items = []
        for i in getattr(doc, "doc_items", []):
            items.append(
                WarehouseDocItemResponse(
                    id=i.id,
                    item_id=i.item_id,
                    quantity=i.quantity,
                    purchase_unit_price=i.purchase_unit_price,
                    unit_price_net=i.unit_price_net,
                    vat_rate=i.vat_rate,
                    suggested_sale_price=i.suggested_sale_price,
                    suggested_sale_price_mode=i.suggested_sale_price_mode,
                    fifo_movements=(fifo_by_item_id or {}).get(i.id, []),
                )
            )
        return cls(
            id=doc.id,  # type: ignore[attr-defined]
            number=doc.number,  # type: ignore[attr-defined]
            doc_type=doc.doc_type,  # type: ignore[attr-defined]
            status=doc.status,  # type: ignore[attr-defined]
            notes=doc.notes,  # type: ignore[attr-defined]
            correction_reason=doc.correction_reason,  # type: ignore[attr-defined]
            issue_reason=doc.issue_reason,  # type: ignore[attr-defined]
            source_invoice_id=doc.source_invoice_id,  # type: ignore[attr-defined]
            fiscal_report_id=doc.fiscal_report_id,  # type: ignore[attr-defined]
            created_at=doc.created_at,  # type: ignore[attr-defined]
            posted_at=doc.posted_at,  # type: ignore[attr-defined]
            items=items,
        )


class WarehouseDocUpdateRequest(BaseModel):
    """Aktualizacja draftu — doc_type jest niezmienny po utworzeniu."""
    items: list[WarehouseDocItemInput]
    notes: str | None = None
    correction_reason: str | None = None
    issue_reason: str | None = None


class WarehouseDocListResponse(BaseModel):
    items: list[WarehouseDocResponse]
    total: int
