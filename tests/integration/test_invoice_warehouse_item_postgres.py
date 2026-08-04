"""GWO-IFG-STOCK-0002C — PostgreSQL integration: InvoiceItem ↔ WarehouseItem.

Wymaga GWO_0002C_DATABASE_URL (lub DATABASE_URL) = postgresql… lokalna kopia.
Nie łączy się z produkcją DS723+.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import AuthenticatedUser
from app.domain.exceptions import InvalidInvoiceError
from app.persistence.models.contractor import ContractorORM
from app.persistence.models.invoice_item import InvoiceItemORM
from app.persistence.models.user import UserORM
from app.persistence.models.warehouse_item import WarehouseItemORM
from app.persistence.repositories.audit_repository import AuditRepository
from app.persistence.repositories.contractor_override_repository import (
    ContractorOverrideRepository,
)
from app.persistence.repositories.contractor_repository import ContractorRepository
from app.persistence.repositories.inventory_layer_repository import (
    InventoryLayerRepository,
)
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.warehouse_document_repository import (
    WarehouseDocumentRepository,
)
from app.services.audit_service import AuditService
from app.services.invoice_service import InvoiceService
from app.services.warehouse_document_service import WarehouseDocumentService

_DB_URL = os.environ.get("GWO_0002C_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
_PG_READY = _DB_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not _PG_READY,
    reason="Wymaga GWO_0002C_DATABASE_URL / DATABASE_URL = postgresql…",
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_DB_URL, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def actor(db: Session) -> AuthenticatedUser:
    user = UserORM(
        username=f"gwo2c_{uuid4().hex[:8]}",
        password_hash="hash",
        role="administrator",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return AuthenticatedUser(user_id=str(user.id), username=user.username, role=user.role)


def _svc(db: Session) -> InvoiceService:
    return InvoiceService(
        session=db,
        invoice_repository=InvoiceRepository(db),
        contractor_repository=ContractorRepository(db),
        contractor_override_repository=ContractorOverrideRepository(db),
        audit_service=AuditService(session=db, audit_repository=AuditRepository(db)),
    )


def _buyer(db: Session) -> ContractorORM:
    nip = f"{uuid4().int % 10**10:010d}"
    buyer = ContractorORM(
        nip=nip,
        name="Nabywca GWO-0002C",
        source="manual",
        street="ul. Test",
        building_no="1",
        postal_code="00-001",
        city="Warszawa",
    )
    db.add(buyer)
    db.flush()
    return buyer


def _warehouse_item(db: Session, *, active: bool = True) -> WarehouseItemORM:
    item = WarehouseItemORM(
        id=uuid4(),
        name=f"Towar {uuid4().hex[:6]}",
        item_type="goods",
        vat_rate=Decimal("23"),
        default_price_net=Decimal("10.00"),
        suggested_sale_price=Decimal("15.00"),
        suggested_sale_price_mode="net",
        unit="szt.",
        is_warehouse_active=True,
        is_active=active,
    )
    db.add(item)
    db.flush()
    return item


def _create_payload(buyer_id, warehouse_item_id=None, *, direction: str = "sale"):
    item = {
        "name": "Pozycja testowa",
        "quantity": 2,
        "unit": "szt.",
        "unit_price_net": "10.00",
        "vat_rate": "23",
    }
    if warehouse_item_id is not None:
        item["warehouse_item_id"] = warehouse_item_id
    payload = {
        "buyer_id": buyer_id,
        "issue_date": date(2026, 8, 4),
        "sale_date": date(2026, 8, 4),
        "due_date": date(2026, 8, 18),
        "payment_method": "transfer",
        "direction": direction,
        "items": [item],
    }
    return payload


def _settings_ctx(override_settings):
    return override_settings(
        seller_nip="1000000035",
        seller_name="Sprzedawca GWO",
        seller_street="ul. Sprzedawcy",
        seller_building_no="1",
        seller_apartment_no=None,
        seller_postal_code="00-001",
        seller_city="Warszawa",
        seller_country="PL",
    )


class TestInvoiceWarehouseItemPostgres:
    def test_create_with_warehouse_item_id_persists_and_rereads(
        self, db, actor, override_settings
    ):
        buyer = _buyer(db)
        wi = _warehouse_item(db)
        svc = _svc(db)
        with _settings_ctx(override_settings):
            created = svc.create_invoice(_create_payload(buyer.id, wi.id), actor)
        assert created.items[0].warehouse_item_id == wi.id

        reread = svc.get_invoice(created.id)
        assert reread.items[0].warehouse_item_id == wi.id

        row = db.execute(
            select(InvoiceItemORM).where(InvoiceItemORM.invoice_id == created.id)
        ).scalar_one()
        assert row.warehouse_item_id == wi.id

    def test_create_with_null_warehouse_item_id(self, db, actor, override_settings):
        buyer = _buyer(db)
        svc = _svc(db)
        with _settings_ctx(override_settings):
            created = svc.create_invoice(_create_payload(buyer.id, None), actor)
        assert created.items[0].warehouse_item_id is None
        reread = svc.get_invoice(created.id)
        assert reread.items[0].warehouse_item_id is None

    def test_missing_warehouse_item_rolls_back(self, db, actor, override_settings):
        buyer = _buyer(db)
        svc = _svc(db)
        missing = uuid4()
        before = db.execute(text("SELECT count(*) FROM invoices")).scalar()
        with _settings_ctx(override_settings):
            with pytest.raises(InvalidInvoiceError, match="nie istnieje"):
                svc.create_invoice(_create_payload(buyer.id, missing), actor)
        after = db.execute(text("SELECT count(*) FROM invoices")).scalar()
        assert after == before

    def test_delete_used_warehouse_item_restricted(self, db, actor, override_settings):
        buyer = _buyer(db)
        wi = _warehouse_item(db)
        svc = _svc(db)
        with _settings_ctx(override_settings):
            svc.create_invoice(_create_payload(buyer.id, wi.id), actor)
        db.flush()
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.execute(
                    text("DELETE FROM warehouse_items WHERE id = CAST(:id AS uuid)"),
                    {"id": str(wi.id)},
                )
                db.flush()

    def test_deactivate_does_not_break_historical_read(
        self, db, actor, override_settings
    ):
        buyer = _buyer(db)
        wi = _warehouse_item(db)
        svc = _svc(db)
        with _settings_ctx(override_settings):
            created = svc.create_invoice(_create_payload(buyer.id, wi.id), actor)
        wi.is_active = False
        db.flush()
        reread = svc.get_invoice(created.id)
        assert reread.items[0].warehouse_item_id == wi.id
        assert reread.items[0].name == "Pozycja testowa"

    def test_create_invoice_does_not_touch_warehouse_state(
        self, db, actor, override_settings
    ):
        buyer = _buyer(db)
        wi = _warehouse_item(db)
        bal_before = db.execute(text("SELECT count(*) FROM warehouse_balance")).scalar()
        layers_before = db.execute(text("SELECT count(*) FROM inventory_layers")).scalar()
        docs_before = db.execute(text("SELECT count(*) FROM warehouse_documents")).scalar()
        moves_before = db.execute(text("SELECT count(*) FROM stock_movements")).scalar()

        svc = _svc(db)
        with _settings_ctx(override_settings):
            svc.create_invoice(_create_payload(buyer.id, wi.id), actor)
        db.flush()

        assert db.execute(text("SELECT count(*) FROM warehouse_balance")).scalar() == bal_before
        assert db.execute(text("SELECT count(*) FROM inventory_layers")).scalar() == layers_before
        assert db.execute(text("SELECT count(*) FROM warehouse_documents")).scalar() == docs_before
        assert db.execute(text("SELECT count(*) FROM stock_movements")).scalar() == moves_before

    def test_manual_pz_still_works_after_invoice_link(
        self, db, actor, override_settings
    ):
        buyer = _buyer(db)
        wi = _warehouse_item(db)
        svc = _svc(db)
        with _settings_ctx(override_settings):
            inv = svc.create_invoice(_create_payload(buyer.id, wi.id), actor)

        wh_svc = WarehouseDocumentService(
            session=db,
            doc_repo=WarehouseDocumentRepository(db),
            layer_repo=InventoryLayerRepository(db),
        )
        doc = wh_svc.create_document(
            {
                "doc_type": "PZ",
                "items": [
                    {
                        "item_id": wi.id,
                        "quantity": "5",
                        "purchase_unit_price": "8.00",
                    }
                ],
            }
        )
        assert doc.id is not None
        assert inv.items[0].warehouse_item_id == wi.id
        assert doc.source_invoice_id is None

    def test_ksef_style_null_link_still_ok(self, db, actor, override_settings):
        buyer = _buyer(db)
        svc = _svc(db)
        with _settings_ctx(override_settings):
            created = svc.create_invoice(
                _create_payload(buyer.id, None, direction="purchase"),
                actor,
            )
        assert created.direction == "purchase"
        assert created.items[0].warehouse_item_id is None
