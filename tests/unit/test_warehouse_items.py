"""Testy kartoteki magazynowej — cena netto i VAT tylko z PZ."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.routers.warehouse_items import list_balance
from app.persistence.models.warehouse_item import WarehouseItemORM
from app.persistence.repositories.warehouse_item_repository import WarehouseItemRepository
from app.schemas.warehouse_item import WarehouseItemCreateRequest, WarehouseItemUpdateRequest
from app.services.warehouse_item_service import WarehouseItemService
from tests.unit.test_warehouse_documents import (
    ITEM_ID,
    _make_service as _make_doc_service,
    _pz_body,
    _wz_body,
)


def _make_service() -> tuple[WarehouseItemService, MagicMock]:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock(side_effect=lambda obj: obj)
    repo = MagicMock(spec=WarehouseItemRepository)
    svc = WarehouseItemService(session=session, repository=repo)
    return svc, repo


def _active_layers_as_rows(layer_repo) -> list[SimpleNamespace]:
    """Symuluje wiersze SQL zwracane przez list_balance_layers dla aktywnych warstw."""
    rows = []
    for i, layer in enumerate(layer_repo._layers, start=1):
        if layer.remaining_quantity == 0:
            continue
        rows.append(
            SimpleNamespace(
                layer_id=layer.id,
                item_id=layer.item_id,
                remaining_quantity=layer.remaining_quantity,
                purchase_unit_price=layer.purchase_unit_price,
                received_date=layer.received_date or date(2026, 5, 22),
                name="Książka",
                isbn=None,
                unit="szt.",
                item_vat_rate=Decimal("23"),
                source_document_number=f"PZ/2026/{i:04d}",
                source_document_posted_at=None,
                doc_item_vat_rate=Decimal("23"),
            )
        )
    return rows


def _balance_service_for_layers(layer_repo) -> WarehouseItemService:
    session = MagicMock()
    session.execute.return_value.all.return_value = _active_layers_as_rows(layer_repo)
    return WarehouseItemService(session=session, repository=MagicMock(spec=WarehouseItemRepository))


class TestCatalogWriteSchema:
    def test_create_rejects_manual_vat_and_price(self):
        with pytest.raises(ValidationError):
            WarehouseItemCreateRequest(
                name="Książka",
                vat_rate="23",
                default_price_net="10.00",
            )

    def test_update_rejects_manual_vat_and_price(self):
        with pytest.raises(ValidationError):
            WarehouseItemUpdateRequest(vat_rate="8", default_price_net="15.00")


class TestCatalogService:
    def test_create_does_not_set_price_or_vat_from_request(self):
        svc, repo = _make_service()
        body = WarehouseItemCreateRequest(name="Książka")

        item = svc.create(body)

        repo.add.assert_called_once()
        created: WarehouseItemORM = repo.add.call_args[0][0]
        assert created.name == "Książka"
        assert created.default_price_net is None
        assert created.vat_rate is None

    def test_update_ignores_price_and_vat_fields(self):
        svc, repo = _make_service()
        item_id = uuid4()
        existing = WarehouseItemORM(
            id=item_id,
            name="Książka",
            item_type="goods",
            vat_rate=Decimal("23"),
            default_price_net=Decimal("10.00"),
            unit="szt.",
            is_warehouse_active=True,
            is_active=True,
        )
        repo.get_by_id.return_value = existing

        body = WarehouseItemUpdateRequest(name="Nowa nazwa")
        updated = svc.update(item_id, body)

        assert updated.name == "Nowa nazwa"
        assert updated.default_price_net == Decimal("10.00")
        assert updated.vat_rate == Decimal("23")


class TestBalanceEndpointLayers:
    """GET /warehouse/items/balance — warstwy FIFO, nie suma per towar."""

    def test_two_pz_same_item_returns_two_balance_rows(self):
        doc_svc, _, layer_repo = _make_doc_service()

        pz1 = doc_svc.create_document(_pz_body(qty="5", price="10.00"))
        doc_svc.post_document(pz1.id)
        pz2 = doc_svc.create_document(_pz_body(qty="3", price="15.00"))
        doc_svc.post_document(pz2.id)

        item_svc = _balance_service_for_layers(layer_repo)
        response = list_balance(svc=item_svc, _=MagicMock())

        assert response.total == 2
        assert len(response.items) == 2
        assert all(e.item_id == ITEM_ID for e in response.items)
        assert {e.unit_price_net for e in response.items} == {
            Decimal("10.00"),
            Decimal("15.00"),
        }
        assert sum(e.quantity_available for e in response.items) == Decimal("8")

    def test_wz_fifo_excludes_depleted_layer(self):
        doc_svc, _, layer_repo = _make_doc_service()

        pz1 = doc_svc.create_document(_pz_body(qty="10", price="20.00"))
        doc_svc.post_document(pz1.id)
        pz2 = doc_svc.create_document(_pz_body(qty="5", price="24.00"))
        doc_svc.post_document(pz2.id)
        wz = doc_svc.create_document(_wz_body(qty="12"))
        doc_svc.post_document(wz.id)

        item_svc = _balance_service_for_layers(layer_repo)
        response = list_balance(svc=item_svc, _=MagicMock())

        assert response.total == 1
        depleted = [l for l in layer_repo._layers if l.remaining_quantity == 0]
        assert len(depleted) == 1
        assert depleted[0].purchase_unit_price == Decimal("20.00")

    def test_wz_fifo_second_layer_has_correct_qty_and_price(self):
        doc_svc, _, layer_repo = _make_doc_service()

        pz1 = doc_svc.create_document(_pz_body(qty="10", price="20.00"))
        doc_svc.post_document(pz1.id)
        pz2 = doc_svc.create_document(_pz_body(qty="5", price="24.00"))
        doc_svc.post_document(pz2.id)
        wz = doc_svc.create_document(_wz_body(qty="12"))
        doc_svc.post_document(wz.id)

        item_svc = _balance_service_for_layers(layer_repo)
        response = list_balance(svc=item_svc, _=MagicMock())

        assert len(response.items) == 1
        row = response.items[0]
        assert row.unit_price_net == Decimal("24.00")
        assert row.quantity_available == Decimal("3")
        assert row.value_net == Decimal("72.00")

    def test_zero_quantity_layer_not_returned(self):
        doc_svc, _, layer_repo = _make_doc_service()

        pz1 = doc_svc.create_document(_pz_body(qty="5", price="10.00"))
        doc_svc.post_document(pz1.id)
        pz2 = doc_svc.create_document(_pz_body(qty="5", price="12.00"))
        doc_svc.post_document(pz2.id)
        wz = doc_svc.create_document(_wz_body(qty="5"))
        doc_svc.post_document(wz.id)

        item_svc = _balance_service_for_layers(layer_repo)
        entries = item_svc.list_balance_layers()

        assert len(entries) == 1
        assert entries[0].unit_price_net == Decimal("12.00")
        assert all(l.remaining_quantity != 0 for l in layer_repo._layers if l.id == entries[0].layer_id)
        assert any(l.remaining_quantity == 0 for l in layer_repo._layers)
