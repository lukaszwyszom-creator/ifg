"""Testy jednostkowe serwisu dokumentów magazynowych (FIFO).

Repozytoria są zastąpione lekkimi fake'ami — brak zależności od bazy danych.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.exceptions import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    InvalidWarehouseDocumentError,
)
from app.persistence.models.inventory_layer import InventoryLayerMovementORM, InventoryLayerORM
from app.persistence.models.warehouse_document import (
    WarehouseDocumentItemORM,
    WarehouseDocumentORM,
)
from app.persistence.models.warehouse_item import WarehouseItemORM
from app.services.warehouse_document_service import WarehouseDocumentService


class _FakeBalance:
    """Lekki zastępnik WarehouseBalanceORM bez SQLAlchemy instrumentation."""
    __slots__ = ("item_id", "quantity_available")

    def __init__(self, item_id, quantity_available):
        self.item_id = item_id
        self.quantity_available = Decimal(str(quantity_available))

# ─────────────────────────────────────────────────────────────────────────────
# Fake repozytoria (in-memory)
# ─────────────────────────────────────────────────────────────────────────────

class FakeDocumentRepository:
    def __init__(self) -> None:
        self._docs: dict[UUID, WarehouseDocumentORM] = {}
        self._balances: dict[UUID, WarehouseBalanceORM] = {}
        self._seq_counters: dict[tuple[str, int], int] = {}

    def get_by_id(self, doc_id: UUID) -> WarehouseDocumentORM | None:
        return self._docs.get(doc_id)

    def get_by_id_with_items(self, doc_id: UUID) -> WarehouseDocumentORM | None:
        return self._docs.get(doc_id)

    def list_all(self, **kwargs) -> list[WarehouseDocumentORM]:
        return list(self._docs.values())

    def count(self, **kwargs) -> int:
        return len(self._docs)

    def add(self, doc: WarehouseDocumentORM) -> WarehouseDocumentORM:
        self._docs[doc.id] = doc
        return doc

    def save(self, doc: WarehouseDocumentORM) -> WarehouseDocumentORM:
        if doc.number:
            owner = next(
                (
                    existing
                    for existing in self._docs.values()
                    if existing.number == doc.number and existing.id != doc.id
                ),
                None,
            )
            if owner is not None:
                raise ValueError(f"duplicate document number: {doc.number}")
        self._docs[doc.id] = doc
        return doc

    def allocate_next_sequence(self, doc_type: str, year: int) -> int:
        key = (doc_type, year)
        self._seq_counters[key] = self._seq_counters.get(key, 0) + 1
        return self._seq_counters[key]

    def get_balance(self, item_id: UUID) -> WarehouseBalanceORM | None:
        return self._balances.get(item_id)

    def upsert_balance(self, item_id: UUID, delta) -> _FakeBalance:
        d = Decimal(str(delta))
        bal = self._balances.get(item_id)
        if bal is None:
            bal = _FakeBalance(item_id=item_id, quantity_available=d)
            self._balances[item_id] = bal
        else:
            bal.quantity_available += d
        return bal


class FakeLayerRepository:
    def __init__(self) -> None:
        self._layers: list[InventoryLayerORM] = []
        self._movements: list[InventoryLayerMovementORM] = []

    def get_by_source_document_item_id(
        self, source_document_item_id: UUID
    ) -> InventoryLayerORM | None:
        for layer in self._layers:
            if layer.source_document_item_id == source_document_item_id:
                return layer
        return None

    def delete_layer(self, layer: InventoryLayerORM) -> None:
        self._layers.remove(layer)

    def get_available_fifo(self, item_id: UUID) -> list[InventoryLayerORM]:
        return sorted(
            [l for l in self._layers if l.item_id == item_id and l.remaining_quantity > 0],
            key=lambda l: (l.received_date, l.created_at),
        )

    def add_layer(self, layer: InventoryLayerORM) -> InventoryLayerORM:
        self._layers.append(layer)
        return layer

    def add_movement(self, movement: InventoryLayerMovementORM) -> InventoryLayerMovementORM:
        self._movements.append(movement)
        return movement

    def save(self, layer: InventoryLayerORM) -> InventoryLayerORM:
        return layer

    def get_movements_for_doc_item(self, doc_item_id: UUID) -> list[InventoryLayerMovementORM]:
        return [m for m in self._movements if m.warehouse_document_item_id == doc_item_id]

    def get_movements_detail_for_doc_item(self, warehouse_document_item_id: UUID) -> list[dict]:
        movements = self.get_movements_for_doc_item(warehouse_document_item_id)
        result: list[dict] = []
        for mv in movements:
            layer = next(l for l in self._layers if l.id == mv.layer_id)
            result.append(
                {
                    "source_document_number": None,
                    "source_document_date": layer.received_date,
                    "quantity_consumed": mv.quantity_consumed,
                    "unit_price_net": mv.purchase_unit_price_snapshot,
                }
            )
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_service() -> tuple[WarehouseDocumentService, FakeDocumentRepository, FakeLayerRepository]:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    doc_repo = FakeDocumentRepository()
    layer_repo = FakeLayerRepository()
    svc = WarehouseDocumentService(session=session, doc_repo=doc_repo, layer_repo=layer_repo)
    return svc, doc_repo, layer_repo


class FkEnforcingLayerRepository(FakeLayerRepository):
    """Symuluje FK inventory_layers.source_document_item_id → warehouse_document_items.id."""

    def __init__(self, doc_repo: FakeDocumentRepository) -> None:
        super().__init__()
        self._doc_repo = doc_repo
        self._persisted_item_ids: set[UUID] = set()

    def mark_items_persisted(self) -> None:
        for doc in self._doc_repo._docs.values():
            for item in doc.doc_items:
                self._persisted_item_ids.add(item.id)

    def add_layer(self, layer: InventoryLayerORM) -> InventoryLayerORM:
        if layer.source_document_item_id not in self._persisted_item_ids:
            raise InvalidWarehouseDocumentError(
                f"FK violation: source_document_item_id={layer.source_document_item_id} "
                "not in warehouse_document_items"
            )
        return super().add_layer(layer)


def _make_service_with_fk_check() -> tuple[
    WarehouseDocumentService, FakeDocumentRepository, FkEnforcingLayerRepository
]:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    doc_repo = FakeDocumentRepository()
    layer_repo = FkEnforcingLayerRepository(doc_repo)

    def _flush() -> None:
        layer_repo.mark_items_persisted()

    session.flush = MagicMock(side_effect=_flush)
    svc = WarehouseDocumentService(session=session, doc_repo=doc_repo, layer_repo=layer_repo)
    return svc, doc_repo, layer_repo


ITEM_ID = uuid4()


def _pz_body(
    item_id: UUID = ITEM_ID,
    qty: str = "10",
    price: str | None = "20.00",
    vat_rate: str | None = None,
) -> dict:
    item: dict = {"item_id": str(item_id), "quantity": qty}
    if price is not None:
        item["purchase_unit_price"] = price
    if vat_rate is not None:
        item["vat_rate"] = vat_rate
    return {
        "doc_type": "PZ",
        "items": [item],
    }


def _wz_body(item_id: UUID = ITEM_ID, qty: str = "5") -> dict:
    """WZ tryb A — powiązany z fakturą sprzedaży (source_invoice_id ustawiony)."""
    return {
        "doc_type": "WZ",
        "source_invoice_id": str(uuid4()),
        "items": [{"item_id": str(item_id), "quantity": qty}],
    }


def _wz_no_invoice_body(
    item_id: UUID = ITEM_ID,
    qty: str = "5",
    issue_reason: str | None = "Podarunek",
    unit_price_net: str | None = None,
) -> dict:
    """WZ tryb B — bez faktury; wymaga issue_reason."""
    body: dict = {
        "doc_type": "WZ",
        "items": [{"item_id": str(item_id), "quantity": qty}],
    }
    if issue_reason is not None:
        body["issue_reason"] = issue_reason
    if unit_price_net is not None:
        body["items"][0]["unit_price_net"] = unit_price_net
    return body


def _kk_body(
    item_id: UUID = ITEM_ID,
    qty: str = "3",
    price: str | None = "20.00",
    reason: str = "Inwentaryzacja",
) -> dict:
    item: dict = {"item_id": str(item_id), "quantity": qty}
    if price is not None:
        item["purchase_unit_price"] = price
    return {
        "doc_type": "KK",
        "correction_reason": reason,
        "items": [item],
    }


def _post_pz_then_get(svc, doc_repo, qty="10", price="20.00"):
    """Pomocnik: tworzy i księguje PZ; zwraca (doc_orm, doc_item_orm)."""
    doc_orm = svc.create_document(_pz_body(qty=qty, price=price))
    # Dołącz doc_items do rekordu (fake ORM nie ładuje relacji — podajemy ręcznie)
    doc_orm.doc_items = [item for item in svc.session.add.call_args_list]  # nie potrzebne
    posted = svc.post_document(doc_orm.id)
    return posted


# ─────────────────────────────────────────────────────────────────────────────
# Testy PZ
# ─────────────────────────────────────────────────────────────────────────────

class TestPZ:
    def test_create_pz_draft_increases_balance(self):
        svc, doc_repo, layer_repo = _make_service()
        svc.create_document(_pz_body(price=None))
        balance = doc_repo.get_balance(ITEM_ID)
        assert balance is not None
        assert balance.quantity_available == Decimal("10")

    def test_create_pz_draft_creates_layer_without_price(self):
        svc, doc_repo, layer_repo = _make_service()
        svc.create_document(_pz_body(qty="10", price=None))
        assert len(layer_repo._layers) == 1
        layer = layer_repo._layers[0]
        assert layer.purchase_unit_price is None
        assert layer.remaining_quantity == Decimal("10")

    def test_post_pz_does_not_increase_balance(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10", price="20.00"))
        balance_before = doc_repo.get_balance(ITEM_ID).quantity_available
        svc.post_document(doc.id)
        assert doc_repo.get_balance(ITEM_ID).quantity_available == balance_before

    def test_post_pz_updates_layer_price_not_quantity(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(doc.id)
        assert len(layer_repo._layers) == 1
        layer = layer_repo._layers[0]
        assert layer.remaining_quantity == Decimal("10")
        assert layer.purchase_unit_price == Decimal("20.00")
        assert layer.source_document_type == "PZ"
        assert layer.is_correction is False

    def test_post_pz_increases_balance(self):
        """Legacy name: balance comes from draft create, not post."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(doc.id)
        balance = doc_repo.get_balance(ITEM_ID)
        assert balance is not None
        assert balance.quantity_available == Decimal("10")

    def test_post_pz_creates_inventory_layer(self):
        """Warstwa powstaje przy create; post tylko uzupełnia cenę."""
        svc, _, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10", price="20.00"))
        assert len(layer_repo._layers) == 1
        assert layer_repo._layers[0].purchase_unit_price is None
        svc.post_document(doc.id)
        assert len(layer_repo._layers) == 1
        assert layer_repo._layers[0].purchase_unit_price == Decimal("20.00")

    def test_post_pz_sets_catalog_vat_rate(self):
        svc, doc_repo, _ = _make_service()
        catalog_item = WarehouseItemORM(
            id=ITEM_ID,
            name="Książka",
            item_type="goods",
            vat_rate=None,
            default_price_net=None,
            unit="szt.",
            is_warehouse_active=True,
            is_active=True,
        )
        svc.session.get.return_value = catalog_item

        doc = svc.create_document(_pz_body(vat_rate="8"))
        svc.post_document(doc.id)

        assert catalog_item.vat_rate == Decimal("8")
        assert catalog_item.default_price_net == Decimal("20.00")

    def test_post_pz_sets_status_and_number(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body())
        svc.post_document(doc.id)

        assert doc.status == "posted"
        assert doc.number is not None
        assert doc.number.startswith("PZ/")

    def test_second_post_is_noop(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10"))
        svc.post_document(doc.id)
        svc.post_document(doc.id)  # drugi call

        # Stan nie podwoił się
        balance = doc_repo.get_balance(ITEM_ID)
        assert balance.quantity_available == Decimal("10")
        assert len(layer_repo._layers) == 1

    def test_pz_without_purchase_price_raises_on_post(self):
        svc, doc_repo, layer_repo = _make_service()
        # Omijamy walidację create przez bezpośrednie złożenie dokumentu
        body = {"doc_type": "PZ", "items": [{"item_id": str(ITEM_ID), "quantity": "5", "purchase_unit_price": "10"}]}
        doc = svc.create_document(body)
        # Usuń cenę z pozycji po zapisie (symulacja brakującej ceny)
        doc.doc_items[0].purchase_unit_price = None
        with pytest.raises(InvalidWarehouseDocumentError, match="purchase_unit_price"):
            svc.post_document(doc.id)

    def test_pz_create_allows_missing_purchase_price(self):
        svc, _, _ = _make_service()
        body = {"doc_type": "PZ", "items": [{"item_id": str(ITEM_ID), "quantity": "5"}]}
        doc = svc.create_document(body)
        assert doc.doc_items[0].purchase_unit_price is None

    def test_pz_number_sequential(self):
        svc, doc_repo, layer_repo = _make_service()
        for _ in range(3):
            doc = svc.create_document(_pz_body())
            svc.post_document(doc.id)

        numbers = [d.number for d in doc_repo._docs.values() if d.number]
        year = date.today().year
        assert f"PZ/{year}/0001" in numbers
        assert f"PZ/{year}/0002" in numbers
        assert f"PZ/{year}/0003" in numbers

    def test_post_pz_does_not_duplicate_layer(self):
        svc, _, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="5", price="12.00"))
        svc.post_document(doc.id)
        svc.post_document(doc.id)
        assert len(layer_repo._layers) == 1

    def test_wz_consumes_draft_pz_layer_before_post(self):
        svc, _, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty="10", price="20.00"))
        wz = svc.create_document(_wz_body(qty="4"))
        svc.post_document(wz.id)
        layer = layer_repo._layers[0]
        assert layer.remaining_quantity == Decimal("6")
        assert layer.purchase_unit_price is None
        assert layer_repo._movements[0].purchase_unit_price_snapshot is None
        svc.post_document(pz.id)
        assert layer.purchase_unit_price == Decimal("20.00")

    def test_cancel_pz_draft_blocked_after_partial_wz(self):
        svc, _, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty="10", price="20.00"))
        wz = svc.create_document(_wz_body(qty="3"))
        svc.post_document(wz.id)
        with pytest.raises(InvalidWarehouseDocumentError, match="częściowy rozchód"):
            svc.cancel_document(pz.id)


# ─────────────────────────────────────────────────────────────────────────────
# Testy WZ
# ─────────────────────────────────────────────────────────────────────────────

class TestWZ:
    def _setup_stock(self, qty: str = "10", price: str = "20.00"):
        """Zwraca svc + doc_repo + layer_repo z już zaksięgowanym PZ."""
        svc, doc_repo, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty=qty, price=price))
        svc.post_document(pz.id)
        return svc, doc_repo, layer_repo

    def test_wz_decreases_balance(self):
        svc, doc_repo, layer_repo = self._setup_stock(qty="10")
        wz = svc.create_document(_wz_body(qty="3"))
        svc.post_document(wz.id)

        balance = doc_repo.get_balance(ITEM_ID)
        assert balance.quantity_available == Decimal("7")

    def test_wz_reduces_layer_remaining(self):
        svc, doc_repo, layer_repo = self._setup_stock(qty="10", price="20.00")
        wz = svc.create_document(_wz_body(qty="4"))
        svc.post_document(wz.id)

        layer = layer_repo._layers[0]
        assert layer.remaining_quantity == Decimal("6")

    def test_wz_creates_movement_records(self):
        svc, doc_repo, layer_repo = self._setup_stock(qty="10", price="20.00")
        wz = svc.create_document(_wz_body(qty="4"))
        svc.post_document(wz.id)

        assert len(layer_repo._movements) == 1
        mv = layer_repo._movements[0]
        assert mv.quantity_consumed == Decimal("4")
        assert mv.purchase_unit_price_snapshot == Decimal("20.00")

    def test_wz_fifo_consumes_oldest_layer_first(self):
        """PZ1: 10 szt @20 zł, PZ2: 5 szt @24 zł — WZ 12 szt → 10 z PZ1, 2 z PZ2."""
        svc, doc_repo, layer_repo = _make_service()

        pz1 = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(pz1.id)

        pz2 = svc.create_document(_pz_body(qty="5", price="24.00"))
        svc.post_document(pz2.id)

        wz = svc.create_document(_wz_body(qty="12"))
        svc.post_document(wz.id)

        layers = layer_repo._layers
        # warstwa PZ1: 10 - 10 = 0 pozostałe
        pz1_layer = next(l for l in layers if l.purchase_unit_price == Decimal("20.00"))
        assert pz1_layer.remaining_quantity == Decimal("0")

        # warstwa PZ2: 5 - 2 = 3 pozostałe
        pz2_layer = next(l for l in layers if l.purchase_unit_price == Decimal("24.00"))
        assert pz2_layer.remaining_quantity == Decimal("3")

        movements = layer_repo._movements
        assert len(movements) == 2
        consumed_from_pz1 = next(m for m in movements if m.purchase_unit_price_snapshot == Decimal("20.00"))
        consumed_from_pz2 = next(m for m in movements if m.purchase_unit_price_snapshot == Decimal("24.00"))
        assert consumed_from_pz1.quantity_consumed == Decimal("10")
        assert consumed_from_pz2.quantity_consumed == Decimal("2")

    def test_wz_below_zero_raises(self):
        svc, doc_repo, layer_repo = self._setup_stock(qty="5")
        wz = svc.create_document(_wz_body(qty="10"))
        with pytest.raises(InsufficientStockError):
            svc.post_document(wz.id)

    def test_wz_on_empty_stock_raises(self):
        svc, _, _ = _make_service()
        wz = svc.create_document(_wz_body(qty="1"))
        with pytest.raises(InsufficientStockError):
            svc.post_document(wz.id)


# ─────────────────────────────────────────────────────────────────────────────
# Testy KK
# ─────────────────────────────────────────────────────────────────────────────

class TestKK:
    def test_positive_kk_increases_balance(self):
        svc, doc_repo, layer_repo = _make_service()
        kk = svc.create_document(_kk_body(qty="5", price="22.00"))
        svc.post_document(kk.id)

        balance = doc_repo.get_balance(ITEM_ID)
        assert balance.quantity_available == Decimal("5")

    def test_positive_kk_creates_correction_layer(self):
        svc, doc_repo, layer_repo = _make_service()
        kk = svc.create_document(_kk_body(qty="5", price="22.00"))
        svc.post_document(kk.id)

        assert len(layer_repo._layers) == 1
        layer = layer_repo._layers[0]
        assert layer.is_correction is True
        assert layer.source_document_type == "KK"
        assert layer.purchase_unit_price == Decimal("22.00")

    def test_positive_kk_without_purchase_price_raises(self):
        svc, _, _ = _make_service()
        with pytest.raises(InvalidWarehouseDocumentError, match="purchase_unit_price"):
            svc.create_document(_kk_body(qty="3", price=None))

    def test_negative_kk_decreases_balance_fifo(self):
        svc, doc_repo, layer_repo = _make_service()
        # Najpierw PZ
        pz = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(pz.id)

        # Ujemna KK
        kk = svc.create_document(_kk_body(qty="-4", price=None, reason="Inwentaryzacja"))
        svc.post_document(kk.id)

        balance = doc_repo.get_balance(ITEM_ID)
        assert balance.quantity_available == Decimal("6")

        layer = layer_repo._layers[0]
        assert layer.remaining_quantity == Decimal("6")

    def test_negative_kk_below_zero_raises(self):
        svc, doc_repo, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty="3"))
        svc.post_document(pz.id)

        kk = svc.create_document(_kk_body(qty="-10", price=None, reason="Korekta"))
        with pytest.raises(InsufficientStockError):
            svc.post_document(kk.id)

    def test_kk_without_reason_raises(self):
        svc, _, _ = _make_service()
        body = {
            "doc_type": "KK",
            "items": [{"item_id": str(ITEM_ID), "quantity": "3", "purchase_unit_price": "10"}],
            # brak correction_reason
        }
        doc = svc.create_document(body)
        with pytest.raises(InvalidWarehouseDocumentError, match="correction_reason"):
            svc.post_document(doc.id)

    def test_negative_kk_creates_movement_records(self):
        svc, doc_repo, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(pz.id)

        kk = svc.create_document(_kk_body(qty="-3", price=None, reason="Korekta"))
        svc.post_document(kk.id)

        assert len(layer_repo._movements) == 1
        mv = layer_repo._movements[0]
        assert mv.quantity_consumed == Decimal("3")
        assert mv.purchase_unit_price_snapshot == Decimal("20.00")


# ─────────────────────────────────────────────────────────────────────────────
# Testy statusów
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentStatuses:
    def test_draft_pz_changes_balance(self):
        svc, doc_repo, _ = _make_service()
        svc.create_document(_pz_body())
        assert doc_repo.get_balance(ITEM_ID).quantity_available == Decimal("10")

    def test_cannot_post_cancelled_document(self):
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        doc.status = "cancelled"
        with pytest.raises(InvalidStatusTransitionError):
            svc.post_document(doc.id)

    def test_second_post_idempotent_balance(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10"))
        svc.post_document(doc.id)
        svc.post_document(doc.id)  # drugi call — no-op

        assert doc_repo.get_balance(ITEM_ID).quantity_available == Decimal("10")
        assert len(layer_repo._layers) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Testy WZ tryb A i B (z fakturą / bez faktury)
# ─────────────────────────────────────────────────────────────────────────────

class TestWZModes:
    def _setup_stock(self, qty: str = "10", price: str = "20.00"):
        svc, doc_repo, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty=qty, price=price))
        svc.post_document(pz.id)
        return svc, doc_repo, layer_repo

    # ── Tryb B — bez faktury ──────────────────────────────────────────────────

    def test_wz_without_invoice_with_reason_passes(self):
        svc, doc_repo, layer_repo = self._setup_stock()
        wz = svc.create_document(_wz_no_invoice_body(qty="3", issue_reason="Podarunek"))
        svc.post_document(wz.id)

        balance = doc_repo.get_balance(ITEM_ID)
        assert balance.quantity_available == Decimal("7")

    def test_wz_without_invoice_decreases_balance_fifo(self):
        svc, doc_repo, layer_repo = self._setup_stock(qty="10", price="20.00")
        wz = svc.create_document(_wz_no_invoice_body(qty="4", issue_reason="Gratis"))
        svc.post_document(wz.id)

        layer = layer_repo._layers[0]
        assert layer.remaining_quantity == Decimal("6")

    def test_wz_without_invoice_creates_movements(self):
        svc, doc_repo, layer_repo = self._setup_stock(qty="10", price="20.00")
        wz = svc.create_document(_wz_no_invoice_body(qty="3", issue_reason="Próbka"))
        svc.post_document(wz.id)

        assert len(layer_repo._movements) == 1
        mv = layer_repo._movements[0]
        assert mv.quantity_consumed == Decimal("3")
        assert mv.purchase_unit_price_snapshot == Decimal("20.00")

    def test_wz_without_invoice_unit_price_net_can_be_null(self):
        svc, doc_repo, layer_repo = self._setup_stock()
        wz = svc.create_document(
            _wz_no_invoice_body(qty="2", issue_reason="Gratis", unit_price_net=None)
        )
        svc.post_document(wz.id)
        assert wz.doc_items[0].unit_price_net is None

    # ── Tryb B bez reason — powinno rzucić błąd ───────────────────────────────

    def test_wz_without_invoice_and_without_reason_raises(self):
        svc, _, _ = self._setup_stock()
        with pytest.raises(InvalidWarehouseDocumentError, match="issue_reason"):
            svc.create_document(_wz_no_invoice_body(qty="3", issue_reason=None))

    # ── Tryb A — z fakturą ────────────────────────────────────────────────────

    def test_wz_with_invoice_does_not_require_reason(self):
        svc, doc_repo, layer_repo = self._setup_stock()
        wz = svc.create_document(_wz_body(qty="5"))  # source_invoice_id ustawiony, brak issue_reason
        svc.post_document(wz.id)

        balance = doc_repo.get_balance(ITEM_ID)
        assert balance.quantity_available == Decimal("5")

    def test_wz_with_invoice_stores_sale_price_snapshot(self):
        svc, doc_repo, layer_repo = self._setup_stock()
        body = {
            "doc_type": "WZ",
            "source_invoice_id": str(uuid4()),
            "items": [{"item_id": str(ITEM_ID), "quantity": "3", "unit_price_net": "150.00"}],
        }
        wz = svc.create_document(body)
        svc.post_document(wz.id)

        assert wz.doc_items[0].unit_price_net == Decimal("150.0000")


# ─────────────────────────────────────────────────────────────────────────────
# Testy ilości całkowitej
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegerQuantity:
    def test_pz_rejects_fractional_quantity(self):
        svc, _, _ = _make_service()
        with pytest.raises(InvalidWarehouseDocumentError, match="całkowitą"):
            svc.create_document(_pz_body(qty="1.5"))

    def test_wz_rejects_fractional_quantity(self):
        svc, _, _ = _make_service()
        with pytest.raises(InvalidWarehouseDocumentError, match="całkowitą"):
            svc.create_document(_wz_body(qty="1.5"))

    def test_kk_rejects_fractional_quantity(self):
        svc, _, _ = _make_service()
        with pytest.raises(InvalidWarehouseDocumentError, match="całkowitą"):
            svc.create_document(_kk_body(qty="1.5"))


# ─────────────────────────────────────────────────────────────────────────────
# Testy immutability POSTED
# ─────────────────────────────────────────────────────────────────────────────

class TestPostedImmutability:
    def test_assert_mutable_raises_for_posted(self):
        from app.services.warehouse_document_service import _assert_mutable
        doc = WarehouseDocumentORM(
            id=uuid4(), doc_type="PZ", status="posted",
        )
        with pytest.raises(InvalidWarehouseDocumentError, match="POSTED"):
            _assert_mutable(doc)

    def test_assert_mutable_raises_for_cancelled(self):
        from app.services.warehouse_document_service import _assert_mutable
        doc = WarehouseDocumentORM(
            id=uuid4(), doc_type="PZ", status="cancelled",
        )
        with pytest.raises(InvalidWarehouseDocumentError, match="CANCELLED"):
            _assert_mutable(doc)

    def test_assert_mutable_passes_for_draft(self):
        from app.services.warehouse_document_service import _assert_mutable
        doc = WarehouseDocumentORM(
            id=uuid4(), doc_type="PZ", status="draft",
        )
        _assert_mutable(doc)  # nie rzuca

    def test_legacy_wz_draft_without_reason_blocked_on_post(self):
        """Draft WZ zapisany przed walidacją (bez issue_reason i source_invoice_id)
        nie może zostać zaksięgowany — guard działa również przy post_document."""
        svc, doc_repo, layer_repo = _make_service()
        pz = svc.create_document(_pz_body(qty="5"))
        svc.post_document(pz.id)

        # Bypass create-validation: wstrzykujemy dokument bezpośrednio do fake repo
        legacy_doc = WarehouseDocumentORM(
            id=uuid4(), doc_type="WZ", status="draft",
        )
        item = WarehouseDocumentItemORM(
            id=uuid4(), document_id=legacy_doc.id,
            item_id=ITEM_ID, quantity=Decimal("3"),
        )
        legacy_doc.doc_items.append(item)
        doc_repo._docs[legacy_doc.id] = legacy_doc

        with pytest.raises(InvalidWarehouseDocumentError, match="issue_reason"):
            svc.post_document(legacy_doc.id)

    def test_cannot_post_posted_document_twice_without_side_effects(self):
        """Drugi POST jest no-op — nie tworzy drugiej warstwy ani nie zmienia salda."""
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="5"))
        svc.post_document(doc.id)
        svc.post_document(doc.id)

        assert len(layer_repo._layers) == 1
        assert doc_repo.get_balance(ITEM_ID).quantity_available == Decimal("5")


# ─────────────────────────────────────────────────────────────────────────────
# Testy edycji i anulowania draftów
# ─────────────────────────────────────────────────────────────────────────────

ITEM_ID_2 = uuid4()  # drugi towar do testów update


def _update_body(
    item_id: UUID = ITEM_ID,
    qty: str = "7",
    price: str = "25.00",
    notes: str = "Zmieniony",
) -> dict:
    return {
        "items": [{"item_id": str(item_id), "quantity": qty, "purchase_unit_price": price}],
        "notes": notes,
    }


class TestDraftEditAndCancel:

    # ── update_document ───────────────────────────────────────────────────────

    def test_update_pz_draft_changes_items(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10", price="20.00"))
        assert doc.doc_items[0].quantity == Decimal("10")

        svc.update_document(doc.id, _update_body(qty="7", price="25.00"))

        updated = doc_repo.get_by_id_with_items(doc.id)
        assert len(updated.doc_items) == 1
        assert updated.doc_items[0].quantity == Decimal("7.0000")
        assert updated.doc_items[0].purchase_unit_price == Decimal("25.0000")

    def test_update_pz_draft_changes_notes(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body())

        svc.update_document(doc.id, _update_body(notes="Nowa notatka"))

        updated = doc_repo.get_by_id_with_items(doc.id)
        assert updated.notes == "Nowa notatka"

    def test_update_wz_draft_changes_items(self):
        svc, doc_repo, layer_repo = _make_service()
        # WZ z fakturą (source_invoice_id ustawiony)
        doc = svc.create_document({
            "doc_type": "WZ",
            "source_invoice_id": str(uuid4()),
            "items": [{"item_id": str(ITEM_ID), "quantity": "3"}],
        })
        assert doc.doc_items[0].quantity == Decimal("3")

        svc.update_document(doc.id, {
            "items": [{"item_id": str(ITEM_ID), "quantity": "5"}],
            "source_invoice_id": str(uuid4()),
        })

        updated = doc_repo.get_by_id_with_items(doc.id)
        assert updated.doc_items[0].quantity == Decimal("5.0000")

    def test_update_draft_syncs_inventory_layers(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body(qty="10"))
        assert len(layer_repo._layers) == 1
        svc.update_document(doc.id, _update_body(qty="7"))
        assert len(layer_repo._layers) == 1
        assert layer_repo._layers[0].remaining_quantity == Decimal("7")
        assert doc_repo.get_balance(ITEM_ID).quantity_available == Decimal("7")

    def test_edit_pz_draft_recreates_layers(self):
        """Regresja: edycja PZ draft wymaga flush pozycji przed utworzeniem warstw FIFO."""
        svc, doc_repo, layer_repo = _make_service_with_fk_check()
        doc = svc.create_document(_pz_body(qty="10", price="20.00"))
        assert len(layer_repo._layers) == 1
        assert layer_repo._layers[0].remaining_quantity == Decimal("10")

        svc.update_document(doc.id, _update_body(qty="7", price="25.00"))

        updated = doc_repo.get_by_id_with_items(doc.id)
        assert len(updated.doc_items) == 1
        assert updated.doc_items[0].quantity == Decimal("7.0000")
        assert len(layer_repo._layers) == 1
        layer = layer_repo.get_by_source_document_item_id(updated.doc_items[0].id)
        assert layer is not None
        assert layer.remaining_quantity == Decimal("7")
        assert layer.received_quantity == Decimal("7")
        assert doc_repo.get_balance(ITEM_ID).quantity_available == Decimal("7")

    def test_update_draft_replaces_all_items(self):
        """Po update stare pozycje są zastąpione nowymi — brak duplikatów."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body(qty="10"))

        # Update z innym towarem
        svc.update_document(doc.id, {
            "items": [
                {"item_id": str(ITEM_ID_2), "quantity": "3", "purchase_unit_price": "15.00"},
            ],
        })

        updated = doc_repo.get_by_id_with_items(doc.id)
        assert len(updated.doc_items) == 1
        assert updated.doc_items[0].item_id == ITEM_ID_2

    def test_update_posted_raises(self):
        """POSTED dokumentu nie można edytować."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        svc.post_document(doc.id)

        with pytest.raises(InvalidWarehouseDocumentError, match="POSTED"):
            svc.update_document(doc.id, _update_body())

    def test_update_cancelled_raises(self):
        """CANCELLED dokumentu nie można edytować."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        svc.cancel_document(doc.id)

        with pytest.raises(InvalidWarehouseDocumentError, match="CANCELLED"):
            svc.update_document(doc.id, _update_body())

    # ── cancel_document ───────────────────────────────────────────────────────

    def test_cancel_draft_sets_cancelled_status(self):
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        assert doc.status == "draft"

        svc.cancel_document(doc.id)

        cancelled = doc_repo.get_by_id(doc.id)
        assert cancelled.status == "cancelled"

    def test_cancel_draft_reverts_balance_and_layers(self):
        svc, doc_repo, layer_repo = _make_service()
        doc = svc.create_document(_pz_body())
        svc.cancel_document(doc.id)
        assert doc_repo.get_balance(ITEM_ID).quantity_available == Decimal("0")
        assert len(layer_repo._layers) == 0

    def test_cancel_posted_raises(self):
        """POSTED dokumentu nie można anulować."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        svc.post_document(doc.id)

        with pytest.raises(InvalidWarehouseDocumentError, match="POSTED"):
            svc.cancel_document(doc.id)

    def test_cancel_already_cancelled_is_noop(self):
        """Anulowanie już anulowanego dokumentu jest no-op."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        svc.cancel_document(doc.id)
        svc.cancel_document(doc.id)  # drugi call — no-op

        assert doc_repo.get_by_id(doc.id).status == "cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# Testy podglądu FIFO w response dokumentu
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentFifoResponse:
    def test_posted_wz_after_two_pz_includes_fifo_movements(self):
        svc, doc_repo, layer_repo = _make_service()

        pz1 = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(pz1.id)
        pz2 = svc.create_document(_pz_body(qty="5", price="24.00"))
        svc.post_document(pz2.id)
        wz = svc.create_document(_wz_body(qty="12"))
        svc.post_document(wz.id)
        doc_repo.get_by_id(wz.id).created_at = datetime.now(timezone.utc)

        resp = svc.get_document_response(wz.id)

        assert resp.status == "posted"
        assert len(resp.items) == 1
        assert len(resp.items[0].fifo_movements) == 2
        assert sum(m.quantity_consumed for m in resp.items[0].fifo_movements) == Decimal("12")
        prices = {m.unit_price_net for m in resp.items[0].fifo_movements}
        assert prices == {Decimal("20.00"), Decimal("24.00")}
        assert len(layer_repo.get_movements_for_doc_item(resp.items[0].id)) == 2

    def test_draft_wz_has_no_fifo_movements(self):
        svc, doc_repo, _ = _make_service()

        pz = svc.create_document(_pz_body(qty="10", price="20.00"))
        svc.post_document(pz.id)
        wz = svc.create_document(_wz_body(qty="5"))
        doc_repo.get_by_id(wz.id).created_at = datetime.now(timezone.utc)

        resp = svc.get_document_response(wz.id)

        assert resp.status == "draft"
        assert resp.items[0].fifo_movements == []


# ─────────────────────────────────────────────────────────────────────────────
# Numeracja dokumentów (atomowy licznik, brak count())
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentNumbering:
    def test_draft_has_no_number(self):
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())

        stored = doc_repo.get_by_id(doc.id)
        assert stored.status == "draft"
        assert stored.number is None

    def test_posted_document_has_number(self):
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        svc.post_document(doc.id)

        stored = doc_repo.get_by_id(doc.id)
        assert stored.status == "posted"
        assert stored.number is not None
        assert stored.number.startswith("PZ/")

    def test_two_documents_same_type_get_different_numbers(self):
        svc, doc_repo, _ = _make_service()
        year = date.today().year

        doc1 = svc.create_document(_pz_body())
        doc2 = svc.create_document(_pz_body())
        svc.post_document(doc1.id)
        svc.post_document(doc2.id)

        assert doc_repo.get_by_id(doc1.id).number == f"PZ/{year}/0001"
        assert doc_repo.get_by_id(doc2.id).number == f"PZ/{year}/0002"
        assert doc_repo.get_by_id(doc1.id).number != doc_repo.get_by_id(doc2.id).number

    def test_pz_and_wz_have_independent_sequences(self):
        svc, doc_repo, _ = _make_service()
        year = date.today().year

        pz = svc.create_document(_pz_body(qty="10"))
        svc.post_document(pz.id)

        wz = svc.create_document(_wz_body(qty="2"))
        svc.post_document(wz.id)

        assert doc_repo.get_by_id(pz.id).number == f"PZ/{year}/0001"
        assert doc_repo.get_by_id(wz.id).number == f"WZ/{year}/0001"

    def test_unique_number_constraint_rejects_duplicate(self):
        svc, doc_repo, _ = _make_service()
        year = date.today().year
        duplicate = f"PZ/{year}/0099"

        doc1 = svc.create_document(_pz_body())
        svc.post_document(doc1.id)

        doc2 = svc.create_document(_pz_body())
        svc.post_document(doc2.id)
        doc_repo.get_by_id(doc2.id).number = duplicate
        doc_repo.get_by_id(doc1.id).number = duplicate

        with pytest.raises(ValueError, match="duplicate document number"):
            doc_repo.save(doc_repo.get_by_id(doc2.id))

    def test_posted_without_number_blocked_by_service(self):
        """POSTED bez numeru nie powstaje przez post_document — numer nadawany przed statusem."""
        svc, doc_repo, _ = _make_service()
        doc = svc.create_document(_pz_body())
        svc.post_document(doc.id)

        stored = doc_repo.get_by_id(doc.id)
        assert stored.status == "posted"
        assert stored.number is not None
