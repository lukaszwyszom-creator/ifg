"""Testy widoku stanów magazynowych jako warstw FIFO."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.persistence.repositories.warehouse_item_repository import WarehouseItemRepository
from app.services.warehouse_item_service import WarehouseItemService, _balance_entry_from_row
from tests.unit.test_warehouse_documents import (
    ITEM_ID,
    _make_service,
    _pz_body,
    _wz_body,
)


def _make_item_service(session: MagicMock | None = None) -> WarehouseItemService:
    session = session or MagicMock()
    return WarehouseItemService(session=session, repository=MagicMock(spec=WarehouseItemRepository))


def _row(
    *,
    layer_id=None,
    item_id=None,
    remaining_quantity="5",
    purchase_unit_price="20.00",
    received_date=None,
    name="Książka",
    isbn="123-45-678912-3-4",
    unit="szt.",
    item_vat_rate=None,
    source_document_number="PZ/2026/0001",
    source_document_posted_at=None,
    doc_item_vat_rate="23",
):
    price_val = None if purchase_unit_price is None else Decimal(purchase_unit_price)
    return SimpleNamespace(
        layer_id=layer_id or uuid4(),
        item_id=item_id or ITEM_ID,
        remaining_quantity=Decimal(remaining_quantity),
        purchase_unit_price=price_val,
        received_date=received_date or date(2026, 5, 22),
        name=name,
        isbn=isbn,
        unit=unit,
        item_vat_rate=Decimal(item_vat_rate) if item_vat_rate is not None else None,
        source_document_number=source_document_number,
        source_document_posted_at=source_document_posted_at
        or datetime(2026, 5, 22, 10, 0, tzinfo=timezone.utc),
        doc_item_vat_rate=Decimal(doc_item_vat_rate) if doc_item_vat_rate is not None else None,
    )


class TestBalanceLayerMapping:
    def test_maps_row_to_layer_response(self):
        row = _row(remaining_quantity="3", purchase_unit_price="10.00", doc_item_vat_rate="8")
        entry = _balance_entry_from_row(row)

        assert entry.quantity_available == Decimal("3")
        assert entry.unit_price_net == Decimal("10.00")
        assert entry.vat_rate == Decimal("8")
        assert entry.value_net == Decimal("30.00")
        assert entry.source_document_number == "PZ/2026/0001"
        assert entry.source_document_date == date(2026, 5, 22)

    def test_vat_falls_back_to_item_rate(self):
        row = _row(doc_item_vat_rate=None, item_vat_rate="5")
        entry = _balance_entry_from_row(row)
        assert entry.vat_rate == Decimal("5")

    def test_null_price_sets_cost_pending(self):
        row = _row(purchase_unit_price=None, remaining_quantity="4")
        row.purchase_unit_price = None
        entry = _balance_entry_from_row(row)
        assert entry.cost_pending is True
        assert entry.unit_price_net is None
        assert entry.value_net is None
        assert entry.quantity_available == Decimal("4")


class TestBalanceLayersService:
    def test_list_balance_layers_returns_active_layers_only(self):
        session = MagicMock()
        session.execute.return_value.all.return_value = [
            _row(remaining_quantity="4"),
            _row(remaining_quantity="2", purchase_unit_price="15.00"),
        ]
        svc = _make_item_service(session)

        entries = svc.list_balance_layers()

        assert len(entries) == 2
        assert entries[0].quantity_available == Decimal("4")
        assert entries[1].unit_price_net == Decimal("15.00")


class TestBalanceLayersFifo:
    """Logika warstw po księgowaniu dokumentów — zgodna z widokiem Stany."""

    def test_two_pz_same_item_produces_two_active_layers(self):
        svc, _, layer_repo = _make_service()

        pz1 = svc.create_document(_pz_body(qty="5", price="10.00"))
        svc.post_document(pz1.id)
        pz2 = svc.create_document(_pz_body(qty="3", price="15.00"))
        svc.post_document(pz2.id)

        active = [l for l in layer_repo._layers if l.remaining_quantity != 0]
        assert len(active) == 2
        assert {l.purchase_unit_price for l in active} == {Decimal("10.00"), Decimal("15.00")}

    def test_draft_pz_layer_visible_before_post(self):
        svc, _, layer_repo = _make_service()
        svc.create_document(_pz_body(qty="4", price="10.00"))
        active = [l for l in layer_repo._layers if l.remaining_quantity != 0]
        assert len(active) == 1
        assert active[0].purchase_unit_price is None
        assert active[0].remaining_quantity == Decimal("4")

    def test_wz_fifo_reduces_first_layer_leaves_second(self):
        svc, _, layer_repo = _make_service()

        pz1 = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(pz1.id)
        pz2 = svc.create_document(_pz_body(qty="5", price="24.00"))
        svc.post_document(pz2.id)
        wz = svc.create_document(_wz_body(qty="12"))
        svc.post_document(wz.id)

        active = [l for l in layer_repo._layers if l.remaining_quantity != 0]
        assert len(active) == 1
        assert active[0].purchase_unit_price == Decimal("24.00")
        assert active[0].remaining_quantity == Decimal("3")

        depleted = [l for l in layer_repo._layers if l.remaining_quantity == 0]
        assert len(depleted) == 1
        assert depleted[0].purchase_unit_price == Decimal("20.00")

    def test_zero_remaining_layer_not_in_active_view(self):
        svc, _, layer_repo = _make_service()

        pz1 = svc.create_document(_pz_body(qty="5", price="10.00"))
        svc.post_document(pz1.id)
        pz2 = svc.create_document(_pz_body(qty="5", price="12.00"))
        svc.post_document(pz2.id)
        wz = svc.create_document(_wz_body(qty="5"))
        svc.post_document(wz.id)

        active = [l for l in layer_repo._layers if l.remaining_quantity != 0]
        assert len(active) == 1
        assert active[0].purchase_unit_price == Decimal("12.00")
