from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.enums import WarehouseItemType


_ISBN_RE_WAREHOUSE = __import__("re").compile(r"^\d{3}-\d{2}-\d{6}-\d-\d$")


class WarehouseItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    isbn: str | None = None
    item_type: WarehouseItemType = WarehouseItemType.GOODS
    unit: str = "szt."
    is_warehouse_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nazwa pozycji nie może być pusta.")
        return v

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: str | None) -> str | None:
        if v is not None and v != "" and not _ISBN_RE_WAREHOUSE.match(v):
            raise ValueError("ISBN musi mieć format xxx-xx-xxxxxx-x-x")
        return v or None


class WarehouseItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    isbn: str | None = None
    item_type: WarehouseItemType | None = None
    unit: str | None = None
    is_warehouse_active: bool | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Nazwa pozycji nie może być pusta.")
        return v


class WarehouseItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    isbn: str | None
    item_type: str
    vat_rate: Decimal | None
    default_price_net: Decimal | None
    suggested_sale_price: Decimal | None
    suggested_sale_price_mode: str
    unit: str
    is_warehouse_active: bool
    is_active: bool
    number: str | None
    created_at: datetime
    updated_at: datetime


class WarehouseItemListResponse(BaseModel):
    items: list[WarehouseItemResponse]
    total: int


class WarehouseBalanceEntryResponse(BaseModel):
    """Pojedyncza aktywna warstwa FIFO widoczna w zakładce Stany."""
    layer_id: UUID
    item_id: UUID
    name: str
    isbn: str | None
    unit: str
    source_document_number: str | None
    source_document_date: date | None
    quantity_available: Decimal
    unit_price_net: Decimal | None
    vat_rate: Decimal | None
    value_net: Decimal | None
    cost_pending: bool = False


class WarehouseBalanceListResponse(BaseModel):
    items: list[WarehouseBalanceEntryResponse]
    total: int
