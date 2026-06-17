"""Regresja: model numeracji draft/locked dla faktur sale."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]

from app.core.security import AuthenticatedUser
from app.domain.enums import InvoiceStatus
from app.domain.exceptions import InvalidStatusTransitionError
from app.persistence.base import Base
from app.persistence.models import (  # noqa: F401
    AuditLog,
    BackgroundJob,
    BankTransactionORM,
    ContractorORM,
    ContractorOverrideORM,
    IdempotencyKeyORM,
    InvoiceItemORM,
    InvoiceORM,
    KSeFSessionORM,
    PaymentAllocationORM,
    TransmissionORM,
    UserORM,
)
from app.persistence.repositories.audit_repository import AuditRepository
from app.persistence.repositories.contractor_override_repository import (
    ContractorOverrideRepository,
)
from app.persistence.repositories.contractor_repository import ContractorRepository
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.services.audit_service import AuditService
from app.services.invoice_service import InvoiceService


@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(sqlite_engine):
    connection = sqlite_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def actor(db: Session) -> AuthenticatedUser:
    user = UserORM(
        username=f"admin_{uuid.uuid4().hex[:6]}",
        password_hash="hash",
        role="administrator",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return AuthenticatedUser(user_id=str(user.id), username=user.username, role=user.role)


def _invoice_service(db: Session) -> InvoiceService:
    audit = AuditService(session=db, audit_repository=AuditRepository(db))
    return InvoiceService(
        session=db,
        invoice_repository=InvoiceRepository(db),
        contractor_repository=ContractorRepository(db),
        contractor_override_repository=ContractorOverrideRepository(db),
        audit_service=audit,
    )


def _buyer(db: Session) -> ContractorORM:
    buyer = ContractorORM(
        nip=f"{uuid.uuid4().int % 10**10:010d}",
        name="Nabywca",
        source="manual",
        street="ul. Test",
        building_no="1",
        postal_code="00-001",
        city="Warszawa",
    )
    db.add(buyer)
    db.flush()
    return buyer


def _create_payload(buyer_id: uuid.UUID, *, issue_date: date = date(2026, 6, 15)) -> dict:
    return {
        "buyer_id": buyer_id,
        "issue_date": issue_date,
        "sale_date": issue_date,
        "due_date": date(2026, 6, 29),
        "payment_method": "transfer",
        "currency": "PLN",
        "direction": "sale",
        "items": [
            {
                "name": "Towar",
                "quantity": "1",
                "unit": "szt.",
                "unit_price_net": "100.00",
                "vat_rate": "23",
            }
        ],
    }


def _settings_ctx(override_settings):
    return override_settings(
        seller_nip="1234567890",
        seller_name="Sprzedawca",
        seller_street="ul. Sprzedawcy",
        seller_building_no="1",
        seller_postal_code="00-001",
        seller_city="Warszawa",
        seller_country="PL",
    )


def test_a_create_two_invoices_stable_numbers(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        invoice_a = svc.create_invoice(_create_payload(buyer.id), actor)
        invoice_b = svc.create_invoice(_create_payload(buyer.id), actor)

    assert invoice_a.number_local == "FV/1/06/2026"
    assert invoice_b.number_local == "FV/2/06/2026"
    assert svc.get_invoice(invoice_a.id).number_local == "FV/1/06/2026"
    assert svc.get_invoice(invoice_b.id).number_local == "FV/2/06/2026"


def test_b_delete_middle_draft_renumbers_later_draft(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        invoice_a = svc.create_invoice(_create_payload(buyer.id), actor)
        invoice_b = svc.create_invoice(_create_payload(buyer.id), actor)
        invoice_c = svc.create_invoice(_create_payload(buyer.id), actor)
        svc.delete_sale_invoice(invoice_b.id, actor)

    assert svc.get_invoice(invoice_a.id).number_local == "FV/1/06/2026"
    assert svc.get_invoice(invoice_c.id).number_local == "FV/2/06/2026"


def test_c_locked_invoice_keeps_number_after_delete_middle_draft(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        invoice_a = svc.create_invoice(_create_payload(buyer.id), actor)
        invoice_b = svc.create_invoice(_create_payload(buyer.id), actor)
        invoice_c = svc.create_invoice(_create_payload(buyer.id), actor)

        locked = svc.invoice_repository.lock_for_update(invoice_a.id)
        assert locked is not None
        locked.status = InvoiceStatus.ACCEPTED
        locked.ksef_reference_number = "KSEF-REF-001"
        svc.invoice_repository.update(invoice_a.id, locked)

        svc.delete_sale_invoice(invoice_b.id, actor)

    assert svc.get_invoice(invoice_a.id).number_local == "FV/1/06/2026"
    assert svc.get_invoice(invoice_c.id).number_local == "FV/2/06/2026"


def test_d_new_draft_after_two_locked_gets_max_plus_one(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        invoice_a = svc.create_invoice(_create_payload(buyer.id), actor)
        invoice_b = svc.create_invoice(_create_payload(buyer.id), actor)

        for inv_id in (invoice_a.id, invoice_b.id):
            locked = svc.invoice_repository.lock_for_update(inv_id)
            assert locked is not None
            locked.status = InvoiceStatus.ACCEPTED
            locked.ksef_reference_number = f"KSEF-{inv_id}"
            svc.invoice_repository.update(inv_id, locked)

        invoice_c = svc.create_invoice(_create_payload(buyer.id), actor)

    assert svc.get_invoice(invoice_a.id).number_local == "FV/1/06/2026"
    assert svc.get_invoice(invoice_b.id).number_local == "FV/2/06/2026"
    assert svc.get_invoice(invoice_c.id).number_local == "FV/3/06/2026"


def test_mark_as_ready_does_not_change_existing_number(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        created = svc.create_invoice(_create_payload(buyer.id), actor)
        again = svc.mark_as_ready(created.id, actor)

    assert again.number_local == created.number_local == "FV/1/06/2026"


def test_cannot_delete_locked_invoice(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        invoice = svc.create_invoice(_create_payload(buyer.id), actor)
        locked = svc.invoice_repository.lock_for_update(invoice.id)
        assert locked is not None
        locked.status = InvoiceStatus.ACCEPTED
        svc.invoice_repository.update(invoice.id, locked)

        with pytest.raises(InvalidStatusTransitionError):
            svc.delete_sale_invoice(invoice.id, actor)


def test_create_purchase_has_no_number_local(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    payload = _create_payload(buyer.id)
    payload["direction"] = "purchase"
    with _settings_ctx(override_settings):
        created = svc.create_invoice(payload, actor)

    assert created.direction == "purchase"
    assert created.number_local is None
    assert svc.get_invoice(created.id).number_local is None


def test_update_backfills_missing_sale_number_local(
    db: Session,
    actor: AuthenticatedUser,
    override_settings,
) -> None:
    buyer = _buyer(db)
    svc = _invoice_service(db)
    with _settings_ctx(override_settings):
        created = svc.create_invoice(_create_payload(buyer.id, issue_date=date(2026, 6, 17)), actor)
        orm = db.get(InvoiceORM, created.id)
        assert orm is not None
        orm.number_local = None
        db.flush()
        cleared = svc.get_invoice(created.id)
        assert cleared.number_local is None

        updated = svc.update_invoice(
            created.id,
            _create_payload(buyer.id, issue_date=date(2026, 6, 17)),
            actor,
        )

    assert updated.number_local == "FV/1/06/2026"
    assert svc.get_invoice(created.id).number_local == "FV/1/06/2026"
