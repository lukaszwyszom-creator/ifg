"""E1: nullable purchase_unit_price on inventory layers."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.persistence.models.inventory_layer import InventoryLayerMovementORM, InventoryLayerORM


def test_inventory_layer_accepts_null_purchase_unit_price():
    layer = InventoryLayerORM(
        id=uuid4(),
        item_id=uuid4(),
        source_document_type="PZ",
        received_quantity=Decimal("5"),
        remaining_quantity=Decimal("5"),
        purchase_unit_price=None,
        received_date=__import__("datetime").date.today(),
    )
    assert layer.purchase_unit_price is None


def test_inventory_layer_movement_accepts_null_price_snapshot():
    mv = InventoryLayerMovementORM(
        id=uuid4(),
        layer_id=uuid4(),
        warehouse_document_item_id=uuid4(),
        quantity_consumed=Decimal("1"),
        purchase_unit_price_snapshot=None,
    )
    assert mv.purchase_unit_price_snapshot is None
