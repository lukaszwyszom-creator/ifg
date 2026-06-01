from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.inventory_layer import InventoryLayerMovementORM, InventoryLayerORM
from app.persistence.models.warehouse_document import (
    WarehouseDocumentItemORM,
    WarehouseDocumentORM,
)


class InventoryLayerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_available_fifo(self, item_id: UUID) -> list[InventoryLayerORM]:
        """Zwraca warstwy z remaining_quantity > 0 posortowane FIFO (najstarsza najpierw)."""
        stmt = (
            select(InventoryLayerORM)
            .where(
                InventoryLayerORM.item_id == item_id,
                InventoryLayerORM.remaining_quantity > 0,
            )
            .order_by(InventoryLayerORM.received_date.asc(), InventoryLayerORM.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def add_layer(self, layer: InventoryLayerORM) -> InventoryLayerORM:
        self.session.add(layer)
        self.session.flush()
        return layer

    def add_movement(self, movement: InventoryLayerMovementORM) -> InventoryLayerMovementORM:
        self.session.add(movement)
        self.session.flush()
        return movement

    def save(self, layer: InventoryLayerORM) -> InventoryLayerORM:
        self.session.add(layer)
        self.session.flush()
        return layer

    def get_movements_for_doc_item(
        self, warehouse_document_item_id: UUID
    ) -> list[InventoryLayerMovementORM]:
        stmt = select(InventoryLayerMovementORM).where(
            InventoryLayerMovementORM.warehouse_document_item_id == warehouse_document_item_id
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_movements_detail_for_doc_item(
        self, warehouse_document_item_id: UUID
    ) -> list[dict]:
        """Ruchy FIFO dla pozycji WZ/KK wraz z danymi dokumentu źródłowego warstwy."""
        stmt = (
            select(
                InventoryLayerMovementORM.quantity_consumed,
                InventoryLayerMovementORM.purchase_unit_price_snapshot,
                InventoryLayerORM.received_date,
                WarehouseDocumentORM.number,
                WarehouseDocumentORM.posted_at,
            )
            .join(
                InventoryLayerORM,
                InventoryLayerORM.id == InventoryLayerMovementORM.layer_id,
            )
            .outerjoin(
                WarehouseDocumentItemORM,
                WarehouseDocumentItemORM.id == InventoryLayerORM.source_document_item_id,
            )
            .outerjoin(
                WarehouseDocumentORM,
                WarehouseDocumentORM.id == WarehouseDocumentItemORM.document_id,
            )
            .where(
                InventoryLayerMovementORM.warehouse_document_item_id == warehouse_document_item_id,
            )
            .order_by(InventoryLayerMovementORM.created_at)
        )
        rows = self.session.execute(stmt).all()
        result: list[dict] = []
        for row in rows:
            doc_date = row.posted_at.date() if row.posted_at else row.received_date
            result.append(
                {
                    "source_document_number": row.number,
                    "source_document_date": doc_date,
                    "quantity_consumed": row.quantity_consumed,
                    "unit_price_net": row.purchase_unit_price_snapshot,
                }
            )
        return result
