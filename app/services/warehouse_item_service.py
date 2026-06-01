from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.domain.enums import WarehouseItemType
from app.persistence.models.inventory_layer import InventoryLayerORM
from app.persistence.models.warehouse_document import WarehouseDocumentItemORM, WarehouseDocumentORM
from app.persistence.models.warehouse_item import WarehouseItemORM
from app.persistence.repositories.warehouse_item_repository import WarehouseItemRepository
from app.schemas.warehouse_item import (
    WarehouseBalanceEntryResponse,
    WarehouseItemCreateRequest,
    WarehouseItemUpdateRequest,
)

logger = logging.getLogger(__name__)


class WarehouseItemService:
    def __init__(self, session: Session, repository: WarehouseItemRepository) -> None:
        self.session = session
        self.repo = repository

    def create(self, body: WarehouseItemCreateRequest) -> WarehouseItemORM:
        item = WarehouseItemORM(
            id=uuid4(),
            name=body.name,
            isbn=body.isbn,
            item_type=body.item_type.value,
            unit=body.unit,
            is_warehouse_active=body.is_warehouse_active,
            is_active=True,
        )
        self.repo.add(item)
        self.session.commit()
        self.session.refresh(item)
        logger.info("warehouse_item.created id=%s name=%r", item.id, item.name)
        return item

    def list_items(self, include_inactive: bool = False) -> list[WarehouseItemORM]:
        return self.repo.list_all(include_inactive=include_inactive)

    def get_by_id(self, item_id: UUID) -> WarehouseItemORM:
        item = self.repo.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Pozycja {item_id} nie istnieje.")
        return item

    def update(self, item_id: UUID, body: WarehouseItemUpdateRequest) -> WarehouseItemORM:
        item = self.get_by_id(item_id)
        if body.name is not None:
            item.name = body.name
        if body.isbn is not None:
            item.isbn = body.isbn or None
        if body.item_type is not None:
            item.item_type = body.item_type.value
        if body.unit is not None:
            item.unit = body.unit
        if body.is_warehouse_active is not None:
            item.is_warehouse_active = body.is_warehouse_active
        if body.is_active is not None:
            item.is_active = body.is_active
        self.repo.save(item)
        self.session.commit()
        self.session.refresh(item)
        logger.info("warehouse_item.updated id=%s", item_id)
        return item

    def deactivate(self, item_id: UUID) -> WarehouseItemORM:
        """Soft-deactivate: ustawia is_active=False. Nie usuwa rekordu."""
        item = self.get_by_id(item_id)
        item.is_active = False
        self.repo.save(item)
        self.session.commit()
        self.session.refresh(item)
        logger.info("warehouse_item.deactivated id=%s", item_id)
        return item

    def list_balance_layers(self) -> list[WarehouseBalanceEntryResponse]:
        """Aktywne warstwy FIFO (remaining_quantity != 0) z danymi towaru i dokumentu źródłowego."""
        stmt = (
            select(
                InventoryLayerORM.id.label("layer_id"),
                InventoryLayerORM.item_id,
                InventoryLayerORM.remaining_quantity,
                InventoryLayerORM.purchase_unit_price,
                InventoryLayerORM.received_date,
                WarehouseItemORM.name,
                WarehouseItemORM.isbn,
                WarehouseItemORM.unit,
                WarehouseItemORM.vat_rate.label("item_vat_rate"),
                WarehouseDocumentORM.number.label("source_document_number"),
                WarehouseDocumentORM.posted_at.label("source_document_posted_at"),
                WarehouseDocumentItemORM.vat_rate.label("doc_item_vat_rate"),
            )
            .join(WarehouseItemORM, WarehouseItemORM.id == InventoryLayerORM.item_id)
            .outerjoin(
                WarehouseDocumentItemORM,
                WarehouseDocumentItemORM.id == InventoryLayerORM.source_document_item_id,
            )
            .outerjoin(
                WarehouseDocumentORM,
                WarehouseDocumentORM.id == WarehouseDocumentItemORM.document_id,
            )
            .where(InventoryLayerORM.remaining_quantity != 0)
            .order_by(
                WarehouseItemORM.name,
                InventoryLayerORM.received_date,
                InventoryLayerORM.created_at,
            )
        )
        rows = self.session.execute(stmt).all()
        return [_balance_entry_from_row(r) for r in rows]


def _balance_entry_from_row(row) -> WarehouseBalanceEntryResponse:
    qty = Decimal(str(row.remaining_quantity))
    price = Decimal(str(row.purchase_unit_price))
    vat = row.doc_item_vat_rate if row.doc_item_vat_rate is not None else row.item_vat_rate
    doc_date: date | None = None
    if row.source_document_posted_at is not None:
        doc_date = row.source_document_posted_at.date()
    elif row.received_date is not None:
        doc_date = row.received_date
    return WarehouseBalanceEntryResponse(
        layer_id=row.layer_id,
        item_id=row.item_id,
        name=row.name,
        isbn=row.isbn,
        unit=row.unit,
        source_document_number=row.source_document_number,
        source_document_date=doc_date,
        quantity_available=qty,
        unit_price_net=price,
        vat_rate=vat,
        value_net=qty * price,
    )
