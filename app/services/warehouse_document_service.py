"""Serwis dokumentów magazynowych — FIFO.

Przepływ:
  create_document() → status=DRAFT (nie zmienia stanu)
  post_document()   → status=POSTED (zmienia stany, tworzy warstwy FIFO)

PZ  → tworzy warstwę InventoryLayer; zwiększa WarehouseBalance
WZ  → zdejmuje FIFO z warstw; zmniejsza WarehouseBalance
      Tryb A (z FV): source_invoice_id ustawione; FV jest source of truth cen/ilości.
      Tryb B (bez FV): source_invoice_id=null; wymaga issue_reason; unit_price_net może być null.
KK+ → jak PZ (tworzy warstwę korekcyjną); wymaga purchase_unit_price
KK− → jak WZ (FIFO); zmniejsza WarehouseBalance

Idempotencja POST:
  Drugi call /post dla dokumentu o statusie POSTED jest no-op (bezpieczny).

Immutability:
  Dokument POSTED jest niemodyfikowalny. Każda przyszła ścieżka update
  MUSI wywołać _assert_mutable() przed zmianą.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.domain.enums import WarehouseDocumentStatus, WarehouseDocumentType
from app.domain.exceptions import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    InvalidWarehouseDocumentError,
)
from app.domain.models.warehouse import WarehouseDoc, WarehouseDocItem
from app.persistence.models.inventory_layer import InventoryLayerMovementORM, InventoryLayerORM
from app.persistence.models.warehouse_document import (
    WarehouseDocumentItemORM,
    WarehouseDocumentORM,
)
from app.persistence.models.warehouse_item import WarehouseItemORM
from app.persistence.repositories.inventory_layer_repository import InventoryLayerRepository
from app.persistence.repositories.warehouse_document_repository import (
    WarehouseDocumentRepository,
)
from app.schemas.warehouse_document import (
    WarehouseDocFifoMovementResponse,
    WarehouseDocResponse,
)

logger = logging.getLogger(__name__)

_FOUR = Decimal("0.0001")
_SALE_PRICE_MODE_NET = "net"
_SALE_PRICE_MODE_GROSS = "gross"


def _to_dec(v: object) -> Decimal:
    return Decimal(str(v)).quantize(_FOUR, rounding=ROUND_HALF_UP)


def _resolve_doc_item_suggested_sale_price_mode(raw: dict) -> str | None:
    mode = raw.get("suggested_sale_price_mode")
    if mode is not None:
        if mode not in (_SALE_PRICE_MODE_NET, _SALE_PRICE_MODE_GROSS):
            raise InvalidWarehouseDocumentError(
                "suggested_sale_price_mode musi być 'net' lub 'gross'."
            )
        return mode
    if raw.get("suggested_sale_price") is not None:
        return _SALE_PRICE_MODE_GROSS
    return None


def _build_item_orm(raw: dict, document_id: object) -> WarehouseDocumentItemORM:
    """Buduje WarehouseDocumentItemORM z surowego słownika."""
    return WarehouseDocumentItemORM(
        id=uuid4(),
        document_id=document_id,
        item_id=UUID(str(raw["item_id"])),
        quantity=_to_dec(raw["quantity"]),
        purchase_unit_price=(
            _to_dec(raw["purchase_unit_price"])
            if raw.get("purchase_unit_price") is not None
            else None
        ),
        unit_price_net=(
            _to_dec(raw["unit_price_net"])
            if raw.get("unit_price_net") is not None
            else None
        ),
        vat_rate=(
            _to_dec(raw["vat_rate"])
            if raw.get("vat_rate") is not None
            else None
        ),
        suggested_sale_price=(
            _to_dec(raw["suggested_sale_price"])
            if raw.get("suggested_sale_price") is not None
            else None
        ),
        suggested_sale_price_mode=_resolve_doc_item_suggested_sale_price_mode(raw),
    )


def _allocate_document_number(doc_repo: WarehouseDocumentRepository, doc_type: str, year: int) -> str:
    """Rezerwuje kolejny numer w formacie PZ/2026/0001 (atomowy licznik w DB)."""
    seq = doc_repo.allocate_next_sequence(doc_type, year)
    return f"{doc_type}/{year}/{seq:04d}"


def _assert_mutable(doc: WarehouseDocumentORM) -> None:
    """Rzuca błąd jeśli dokument jest już zaksięgowany lub anulowany.

    Wywoływać na początku każdego endpointu/ścieżki modyfikującej dokument.
    """
    if doc.status == WarehouseDocumentStatus.POSTED.value:
        raise InvalidWarehouseDocumentError(
            f"Dokument {doc.id} jest zaksięgowany (POSTED) i nie może być modyfikowany."
        )
    if doc.status == WarehouseDocumentStatus.CANCELLED.value:
        raise InvalidWarehouseDocumentError(
            f"Dokument {doc.id} jest anulowany (CANCELLED) i nie może być modyfikowany."
        )


class WarehouseDocumentService:
    def __init__(
        self,
        session: Session,
        doc_repo: WarehouseDocumentRepository,
        layer_repo: InventoryLayerRepository,
    ) -> None:
        self.session = session
        self.doc_repo = doc_repo
        self.layer_repo = layer_repo

    # ── Tworzenie draftu ──────────────────────────────────────────────────────

    def create_document(self, body: dict, created_by: UUID | None = None) -> WarehouseDocumentORM:
        """Tworzy dokument w stanie DRAFT. Nie zmienia stanów magazynowych."""
        doc_type = body.get("doc_type", "")
        if doc_type not in (t.value for t in WarehouseDocumentType):
            raise InvalidWarehouseDocumentError(f"Nieznany typ dokumentu: {doc_type!r}")

        raw_items: list[dict] = body.get("items", [])
        if not raw_items:
            raise InvalidWarehouseDocumentError("Dokument musi mieć co najmniej jedną pozycję.")

        self._validate_items_for_type(doc_type, raw_items)
        self._validate_doc_header(doc_type, body)

        doc_orm = WarehouseDocumentORM(
            id=uuid4(),
            doc_type=doc_type,
            status=WarehouseDocumentStatus.DRAFT.value,
            notes=body.get("notes"),
            correction_reason=body.get("correction_reason"),
            issue_reason=body.get("issue_reason"),
            source_invoice_id=body.get("source_invoice_id"),
            fiscal_report_id=body.get("fiscal_report_id"),
            created_by=created_by,
        )
        for raw in raw_items:
            doc_orm.doc_items.append(_build_item_orm(raw, doc_orm.id))

        self.doc_repo.add(doc_orm)
        self.session.flush()
        logger.info("warehouse_document.created id=%s type=%s", doc_orm.id, doc_type)
        return doc_orm

    # ── Księgowanie (POST) ────────────────────────────────────────────────────

    def post_document(self, doc_id: UUID) -> WarehouseDocumentORM:
        """Księguje dokument: zmienia stany magazynowe i tworzy warstwy FIFO.

        Idempotentny: drugi call dla POSTED dokumentu jest no-op.
        Nie można zaksięgować CANCELLED dokumentu.
        """
        doc = self.doc_repo.get_by_id_with_items(doc_id)
        if doc is None:
            raise NotFoundError(f"Dokument {doc_id} nie istnieje.")

        if doc.status == WarehouseDocumentStatus.POSTED.value:
            logger.info("warehouse_document.post.noop id=%s (already posted)", doc_id)
            return doc  # idempotentny

        if doc.status == WarehouseDocumentStatus.CANCELLED.value:
            raise InvalidStatusTransitionError(
                f"Dokument {doc_id} jest anulowany — nie można zaksięgować."
            )

        today = date.today()
        now = datetime.now(UTC)

        if doc.doc_type == WarehouseDocumentType.PZ.value:
            self._post_pz(doc, today)
        elif doc.doc_type == WarehouseDocumentType.WZ.value:
            self._post_wz(doc, today)
        elif doc.doc_type == WarehouseDocumentType.KK.value:
            self._post_kk(doc, today)
        else:
            raise InvalidWarehouseDocumentError(
                f"Typ dokumentu {doc.doc_type!r} nie jest obsługiwany przez post."
            )

        doc.number = _allocate_document_number(self.doc_repo, doc.doc_type, today.year)
        if not doc.number:
            raise InvalidWarehouseDocumentError(
                "Nie udało się nadać numeru dokumentu — księgowanie przerwane."
            )
        doc.status = WarehouseDocumentStatus.POSTED.value
        doc.posted_at = now
        self.doc_repo.save(doc)
        self.session.commit()

        logger.info(
            "warehouse_document.posted id=%s number=%s type=%s",
            doc.id, doc.number, doc.doc_type,
        )
        return doc

    # ── PZ ────────────────────────────────────────────────────────────────────

    def _post_pz(self, doc: WarehouseDocumentORM, today: date) -> None:
        for item in doc.doc_items:
            if item.purchase_unit_price is None:
                raise InvalidWarehouseDocumentError(
                    f"PZ: pozycja {item.id} nie ma ceny zakupu (purchase_unit_price)."
                )
            qty = _to_dec(item.quantity)
            price = _to_dec(item.purchase_unit_price)

            layer = InventoryLayerORM(
                id=uuid4(),
                item_id=item.item_id,
                source_document_item_id=item.id,
                source_document_type=WarehouseDocumentType.PZ.value,
                received_quantity=qty,
                remaining_quantity=qty,
                purchase_unit_price=price,
                received_date=today,
                is_correction=False,
            )
            self.layer_repo.add_layer(layer)
            self.doc_repo.upsert_balance(item.item_id, qty)

            # Zaktualizuj kartotekę towaru danymi z PZ (ostatnia cena zakupu, VAT, cena sugerowana)
            catalog_item = self.session.get(WarehouseItemORM, item.item_id)
            if catalog_item is not None:
                catalog_item.default_price_net = price
                if item.vat_rate is not None:
                    catalog_item.vat_rate = _to_dec(item.vat_rate)
                if item.suggested_sale_price is not None:
                    catalog_item.suggested_sale_price = _to_dec(item.suggested_sale_price)
                    catalog_item.suggested_sale_price_mode = (
                        item.suggested_sale_price_mode or _SALE_PRICE_MODE_GROSS
                    )
                self.session.add(catalog_item)

    # ── WZ ────────────────────────────────────────────────────────────────────

    def _post_wz(self, doc: WarehouseDocumentORM, today: date) -> None:
        # Walidacja trybu B — sprawdź również przy księgowaniu (nie tylko przy create),
        # żeby drafty sprzed tej zmiany nie mogły być zaksięgowane bez wymaganego pola.
        if not doc.source_invoice_id and not doc.issue_reason:
            raise InvalidWarehouseDocumentError(
                "WZ bez faktury (source_invoice_id=null) wymaga podania issue_reason "
                "(podarunek, gratis, próbka, wydanie promocyjne itp.)."
            )
        for item in doc.doc_items:
            qty = _to_dec(item.quantity)
            if qty <= 0:
                raise InvalidWarehouseDocumentError(
                    f"WZ: ilość musi być dodatnia (pozycja {item.id})."
                )
            self._consume_fifo(item.item_id, item.id, qty, doc_type="WZ")
            self.doc_repo.upsert_balance(item.item_id, -qty)

    # ── KK ────────────────────────────────────────────────────────────────────

    def _post_kk(self, doc: WarehouseDocumentORM, today: date) -> None:
        if not doc.correction_reason:
            raise InvalidWarehouseDocumentError(
                "KK wymaga podania correction_reason."
            )
        for item in doc.doc_items:
            qty = _to_dec(item.quantity)
            if qty == 0:
                raise InvalidWarehouseDocumentError(
                    f"KK: ilość nie może wynosić zero (pozycja {item.id})."
                )

            if qty > 0:
                # Dodatnia KK — wymaga ceny zakupu (nowa warstwa korekcyjna)
                if item.purchase_unit_price is None:
                    raise InvalidWarehouseDocumentError(
                        f"KK+: pozycja {item.id} wymaga purchase_unit_price."
                    )
                price = _to_dec(item.purchase_unit_price)
                layer = InventoryLayerORM(
                    id=uuid4(),
                    item_id=item.item_id,
                    source_document_item_id=item.id,
                    source_document_type=WarehouseDocumentType.KK.value,
                    received_quantity=qty,
                    remaining_quantity=qty,
                    purchase_unit_price=price,
                    received_date=today,
                    is_correction=True,
                )
                self.layer_repo.add_layer(layer)
                self.doc_repo.upsert_balance(item.item_id, qty)

            else:
                # Ujemna KK — FIFO deduction
                abs_qty = abs(qty)
                self._consume_fifo(item.item_id, item.id, abs_qty, doc_type="KK")
                self.doc_repo.upsert_balance(item.item_id, -abs_qty)

    # ── FIFO rozchód ──────────────────────────────────────────────────────────

    def _consume_fifo(
        self,
        item_id: UUID,
        doc_item_id: UUID,
        qty_to_consume: Decimal,
        doc_type: str,
    ) -> None:
        """Zdejmuje qty_to_consume z warstw FIFO. Rzuca InsufficientStockError gdy za mało."""
        layers = self.layer_repo.get_available_fifo(item_id)
        total_available = sum(_to_dec(l.remaining_quantity) for l in layers)

        if total_available < qty_to_consume:
            raise InsufficientStockError(
                f"{doc_type}: brak wystarczającego stanu dla pozycji {item_id}. "
                f"Dostępne: {total_available}, wymagane: {qty_to_consume}."
            )

        remaining = qty_to_consume
        for layer in layers:
            if remaining <= 0:
                break
            layer_avail = _to_dec(layer.remaining_quantity)
            take = min(layer_avail, remaining)

            movement = InventoryLayerMovementORM(
                id=uuid4(),
                layer_id=layer.id,
                warehouse_document_item_id=doc_item_id,
                quantity_consumed=take,
                purchase_unit_price_snapshot=_to_dec(layer.purchase_unit_price),
            )
            self.layer_repo.add_movement(movement)

            layer.remaining_quantity = layer_avail - take
            self.layer_repo.save(layer)
            remaining -= take

    # ── Edycja draftu ─────────────────────────────────────────────────────────

    def update_document(self, doc_id: UUID, body: dict) -> WarehouseDocumentORM:
        """Aktualizuje dokument DRAFT. POSTED/CANCELLED są chronione przez _assert_mutable."""
        doc = self.doc_repo.get_by_id_with_items(doc_id)
        if doc is None:
            raise NotFoundError(f"Dokument {doc_id} nie istnieje.")
        _assert_mutable(doc)

        raw_items: list[dict] = body.get("items", [])
        if not raw_items:
            raise InvalidWarehouseDocumentError("Dokument musi mieć co najmniej jedną pozycję.")

        self._validate_items_for_type(doc.doc_type, raw_items)
        self._validate_doc_header(doc.doc_type, body)

        doc.notes = body.get("notes")
        doc.correction_reason = body.get("correction_reason")
        doc.issue_reason = body.get("issue_reason")

        # Zastąp pozycje — usuń stare, dodaj nowe
        for old_item in list(doc.doc_items):
            self.session.delete(old_item)
        doc.doc_items.clear()

        for raw in raw_items:
            doc.doc_items.append(_build_item_orm(raw, doc.id))

        self.doc_repo.save(doc)
        self.session.commit()
        logger.info("warehouse_document.updated id=%s", doc.id)
        return doc

    def cancel_document(self, doc_id: UUID) -> WarehouseDocumentORM:
        """Anuluje dokument DRAFT. POSTED jest chroniony. Idempotentny dla CANCELLED."""
        doc = self.doc_repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError(f"Dokument {doc_id} nie istnieje.")
        if doc.status == WarehouseDocumentStatus.CANCELLED.value:
            return doc  # idempotentny
        _assert_mutable(doc)  # blokuje POSTED

        doc.status = WarehouseDocumentStatus.CANCELLED.value
        self.doc_repo.save(doc)
        self.session.commit()
        logger.info("warehouse_document.cancelled id=%s", doc.id)
        return doc

    # ── Pobieranie ────────────────────────────────────────────────────────────

    def get_document(self, doc_id: UUID) -> WarehouseDocumentORM:
        doc = self.doc_repo.get_by_id_with_items(doc_id)
        if doc is None:
            raise NotFoundError(f"Dokument {doc_id} nie istnieje.")
        return doc

    def get_document_response(self, doc_id: UUID) -> WarehouseDocResponse:
        doc = self.get_document(doc_id)
        fifo_by_item_id: dict[UUID, list[WarehouseDocFifoMovementResponse]] = {}
        if (
            doc.status == WarehouseDocumentStatus.POSTED.value
            and doc.doc_type
            in (WarehouseDocumentType.WZ.value, WarehouseDocumentType.KK.value)
        ):
            for item in doc.doc_items:
                if (
                    doc.doc_type == WarehouseDocumentType.KK.value
                    and _to_dec(item.quantity) > 0
                ):
                    continue
                fifo_by_item_id[item.id] = [
                    WarehouseDocFifoMovementResponse(**row)
                    for row in self.layer_repo.get_movements_detail_for_doc_item(item.id)
                ]
        return WarehouseDocResponse.from_orm(doc, fifo_by_item_id=fifo_by_item_id)

    def list_documents(
        self,
        doc_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WarehouseDocumentORM], int]:
        docs = self.doc_repo.list_all(doc_type=doc_type, status=status, limit=limit, offset=offset)
        total = self.doc_repo.count(doc_type=doc_type, status=status)
        return docs, total

    # ── Walidacja pozycji przed zapisem ──────────────────────────────────────

    @staticmethod
    def _validate_doc_header(doc_type: str, body: dict) -> None:
        """Waliduje pola nagłówka dokumentu zależne od trybu."""
        if doc_type == WarehouseDocumentType.WZ.value:
            source_invoice_id = body.get("source_invoice_id")
            issue_reason = body.get("issue_reason")
            if not source_invoice_id and not issue_reason:
                raise InvalidWarehouseDocumentError(
                    "WZ bez faktury (source_invoice_id=null) wymaga podania issue_reason "
                    "(podarunek, gratis, próbka, wydanie promocyjne itp.)."
                )

    @staticmethod
    def _validate_items_for_type(doc_type: str, raw_items: list[dict]) -> None:
        for i, raw in enumerate(raw_items, 1):
            qty = Decimal(str(raw.get("quantity", 0)))
            if qty == 0:
                raise InvalidWarehouseDocumentError(
                    f"{doc_type}: pozycja {i} — ilość nie może być zerem."
                )
            if qty != qty.to_integral_value():
                raise InvalidWarehouseDocumentError(
                    f"{doc_type}: pozycja {i} — ilość musi być liczbą całkowitą."
                )

        if doc_type == WarehouseDocumentType.PZ.value:
            for i, raw in enumerate(raw_items, 1):
                if raw.get("purchase_unit_price") is None:
                    raise InvalidWarehouseDocumentError(
                        f"PZ: pozycja {i} wymaga purchase_unit_price."
                    )
                if Decimal(str(raw.get("quantity", 0))) <= 0:
                    raise InvalidWarehouseDocumentError(
                        f"PZ: pozycja {i} — ilość musi być dodatnia."
                    )

        elif doc_type == WarehouseDocumentType.WZ.value:
            for i, raw in enumerate(raw_items, 1):
                if Decimal(str(raw.get("quantity", 0))) <= 0:
                    raise InvalidWarehouseDocumentError(
                        f"WZ: pozycja {i} — ilość musi być dodatnia."
                    )

        elif doc_type == WarehouseDocumentType.KK.value:
            for i, raw in enumerate(raw_items, 1):
                qty = Decimal(str(raw.get("quantity", 0)))
                if qty == 0:
                    raise InvalidWarehouseDocumentError(
                        f"KK: pozycja {i} — ilość nie może być zerem."
                    )
                if qty > 0 and raw.get("purchase_unit_price") is None:
                    raise InvalidWarehouseDocumentError(
                        f"KK+: pozycja {i} wymaga purchase_unit_price."
                    )
