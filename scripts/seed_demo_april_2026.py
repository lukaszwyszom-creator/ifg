#!/usr/bin/env python3
"""Deterministyczny seed demo dla kwietnia 2026.

Każdy miesiąc zawiera pełne spektrum payment_status dla sprzedaży i zakupu:
- paid
- partially_paid
- unpaid

Celem jest realistyczny dataset dla rozrachunków i VAT.
Seed intentionally creates paid and partially_paid invoices also for purchases
to simulate real liabilities and cash flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.security import AuthenticatedUser
from app.persistence.db import session_scope
from app.persistence.models.bank_transaction import BankTransactionORM
from app.persistence.models.contractor import ContractorORM
from app.persistence.models.invoice import InvoiceORM
from app.persistence.models.payment_allocation import PaymentAllocationORM
from app.persistence.models.user import UserORM
from app.persistence.repositories.audit_repository import AuditRepository
from app.persistence.repositories.bank_transaction_repository import BankTransactionRepository
from app.persistence.repositories.contractor_override_repository import ContractorOverrideRepository
from app.persistence.repositories.contractor_repository import ContractorRepository
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.payment_allocation_repository import PaymentAllocationRepository
from app.services.audit_service import AuditService
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService

MONEY = Decimal("0.01")
APRIL_START = date(2026, 4, 1)
APRIL_END = date(2026, 5, 1)
SOURCE_FILE = "seed_demo_april_2026.py"


@dataclass(frozen=True)
class ContractorSpec:
    slug: str
    nip: str
    name: str
    city: str
    postal_code: str
    street: str
    building_no: str
    country: str = "PL"


@dataclass(frozen=True)
class InvoiceSpec:
    seed_key: str
    slug: str
    contractor_slug: str
    direction: str
    issue_date: date
    net_amount: Decimal
    vat_rate: Decimal = Decimal("23")


@dataclass(frozen=True)
class TransactionSpec:
    external_id: str
    slug: str
    invoice_slug: str
    amount: Decimal
    transaction_date: date
    title: str


CONTRACTORS = (
    ContractorSpec(
        slug="firma_testowa",
        nip="1234563218",
        name="Firma Testowa Krajowa Sp. z o.o.",
        city="Warszawa",
        postal_code="00-001",
        street="ul. Testowa",
        building_no="1",
    ),
    ContractorSpec(
        slug="ikona",
        nip="9670402857",
        name="IKONA Malgorzata Katarzyna Krzyzanowska-Witkowska",
        city="Bydgoszcz",
        postal_code="85-001",
        street="ul. Dlugosza",
        building_no="12",
    ),
    ContractorSpec(
        slug="deutsche_test",
        nip="DE123456789",
        name="Deutsche Test GmbH",
        city="Berlin",
        postal_code="10115",
        street="Teststrasse",
        building_no="10",
        country="DE",
    ),
    ContractorSpec(
        slug="biuro_rachunkowe_alfa",
        nip="5253001112",
        name="Biuro Rachunkowe Alfa Sp. z o.o.",
        city="Warszawa",
        postal_code="00-105",
        street="ul. Prosta",
        building_no="18",
    ),
    ContractorSpec(
        slug="cloud_services_polska",
        nip="7012345678",
        name="Cloud Services Polska Sp. z o.o.",
        city="Krakow",
        postal_code="30-302",
        street="ul. Kapelanka",
        building_no="42",
    ),
    ContractorSpec(
        slug="office_supply",
        nip="1134567890",
        name="Office Supply Sp. z o.o.",
        city="Poznan",
        postal_code="60-101",
        street="ul. Glogowska",
        building_no="55",
    ),
)

INVOICES = (
    InvoiceSpec("APR2026_SALE_01", "sale_1", "firma_testowa", "sale", date(2026, 4, 5), Decimal("1000.00")),
    InvoiceSpec("APR2026_SALE_02", "sale_2", "ikona", "sale", date(2026, 4, 7), Decimal("2000.00")),
    InvoiceSpec("APR2026_SALE_03", "sale_3", "firma_testowa", "sale", date(2026, 4, 11), Decimal("1500.00")),
    InvoiceSpec("APR2026_SALE_04", "sale_4", "deutsche_test", "sale", date(2026, 4, 18), Decimal("5000.00")),
    InvoiceSpec("APR2026_PURCHASE_01", "purchase_1", "biuro_rachunkowe_alfa", "purchase", date(2026, 4, 3), Decimal("800.00")),
    InvoiceSpec("APR2026_PURCHASE_02", "purchase_2", "cloud_services_polska", "purchase", date(2026, 4, 10), Decimal("1200.00")),
    InvoiceSpec("APR2026_PURCHASE_03", "purchase_3", "cloud_services_polska", "purchase", date(2026, 4, 15), Decimal("2000.00")),
    InvoiceSpec("APR2026_PURCHASE_04", "purchase_4", "office_supply", "purchase", date(2026, 4, 20), Decimal("300.00")),
)

TRANSACTIONS = (
    TransactionSpec("APR2026_TX_01", "tx_sale_1", "sale_1", Decimal("1230.00"), date(2026, 4, 6), "Zapłata demo za FV kwiecien sale_1"),
    TransactionSpec("APR2026_TX_02", "tx_sale_3", "sale_3", Decimal("845.00"), date(2026, 4, 14), "Czesciowa zaplata demo za FV kwiecien sale_3"),
    TransactionSpec("APR2026_TX_03", "tx_purchase_1", "purchase_1", Decimal("984.00"), date(2026, 4, 4), "Platnosc demo za zakup purchase_1"),
    TransactionSpec("APR2026_TX_04", "tx_purchase_3", "purchase_3", Decimal("1000.00"), date(2026, 4, 18), "Czesciowa platnosc demo za zakup purchase_3"),
    TransactionSpec("APR2026_TX_05", "tx_purchase_4", "purchase_4", Decimal("369.00"), date(2026, 4, 22), "Platnosc demo za zakup purchase_4"),
)

ALLOCATIONS = (
    ("tx_sale_1", "sale_1", Decimal("1230.00")),
    ("tx_sale_3", "sale_3", Decimal("845.00")),
    ("tx_purchase_1", "purchase_1", Decimal("984.00")),
    ("tx_purchase_3", "purchase_3", Decimal("1000.00")),
    ("tx_purchase_4", "purchase_4", Decimal("369.00")),
)


class SeederInvoiceRepository(InvoiceRepository):
    def get_orm_by_id(self, invoice_id: UUID) -> InvoiceORM | None:
        return self.session.get(InvoiceORM, invoice_id)


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def build_actor(session) -> AuthenticatedUser:
    stmt = (
        select(UserORM)
        .where(UserORM.is_active.is_(True))
        .order_by((UserORM.username != settings.initial_admin_username).asc(), UserORM.created_at.asc())
    )
    user = session.execute(stmt).scalars().first()
    if user is None:
        raise RuntimeError("Brak aktywnego uzytkownika do wykonania seeda.")
    return AuthenticatedUser(user_id=str(user.id), username=user.username, role=user.role)


def build_services(session):
    audit_service = AuditService(session, AuditRepository(session))
    contractor_repo = ContractorRepository(session)
    contractor_override_repo = ContractorOverrideRepository(session)
    invoice_repo = SeederInvoiceRepository(session)
    tx_repo = BankTransactionRepository(session)
    alloc_repo = PaymentAllocationRepository(session)
    invoice_service = InvoiceService(
        session=session,
        invoice_repository=invoice_repo,
        contractor_repository=contractor_repo,
        contractor_override_repository=contractor_override_repo,
        audit_service=audit_service,
        stock_service=None,
    )
    payment_service = PaymentService(
        session=session,
        bank_transaction_repository=tx_repo,
        allocation_repository=alloc_repo,
        invoice_repository=invoice_repo,
        audit_service=audit_service,
    )
    return contractor_repo, invoice_repo, tx_repo, alloc_repo, invoice_service, payment_service


def ensure_contractors(session, contractor_repo: ContractorRepository) -> dict[str, ContractorORM]:
    existing_by_nip = {
        contractor.nip: contractor
        for contractor in session.execute(select(ContractorORM).where(ContractorORM.nip.in_([spec.nip for spec in CONTRACTORS]))).scalars()
    }
    result: dict[str, ContractorORM] = {}
    for spec in CONTRACTORS:
        contractor = existing_by_nip.get(spec.nip)
        if contractor is None:
            contractor = ContractorORM(
                nip=spec.nip,
                name=spec.name,
                city=spec.city,
                postal_code=spec.postal_code,
                street=spec.street,
                building_no=spec.building_no,
                country=spec.country,
                source="manual",
                source_fetched_at=datetime.now(UTC),
                cache_valid_until=None,
                lookup_last_status=None,
                lookup_last_error=None,
            )
            contractor_repo.add(contractor)
        result[spec.slug] = contractor
    return result


def load_april_invoice_orms(session) -> list[InvoiceORM]:
    stmt = (
        select(InvoiceORM)
        .where(InvoiceORM.issue_date >= APRIL_START, InvoiceORM.issue_date < APRIL_END)
        .order_by(InvoiceORM.issue_date.asc(), InvoiceORM.created_at.asc())
    )
    return list(session.execute(stmt).scalars())


def find_existing_invoice_orm(session, spec: InvoiceSpec, contractor: ContractorORM) -> InvoiceORM | None:
    expected_gross = money(spec.net_amount * (Decimal("1.00") + spec.vat_rate / Decimal("100")))
    matches: list[InvoiceORM] = []
    for orm in load_april_invoice_orms(session):
        if orm.direction != spec.direction:
            continue
        if orm.issue_date != spec.issue_date:
            continue
        buyer_nip = (orm.buyer_snapshot_json or {}).get("nip")
        buyer_name = (orm.buyer_snapshot_json or {}).get("name")
        gross = money((orm.totals_json or {}).get("total_gross", "0.00"))
        if buyer_nip == contractor.nip and buyer_name == contractor.name and gross == expected_gross:
            matches.append(orm)
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"Niejednoznaczny fallback dla {spec.seed_key}: znaleziono {len(matches)} faktury."
        )
    return matches[0]


def ensure_invoice_seed_key(invoice: InvoiceORM, spec: InvoiceSpec) -> None:
    if spec.direction == "sale":
        snapshot = dict(invoice.buyer_snapshot_json or {})
        if "seed_key" in snapshot:
            return
        snapshot["seed_key"] = spec.seed_key
        invoice.buyer_snapshot_json = snapshot
        return

    snapshot = dict(invoice.seller_snapshot_json or {})
    if "seed_key" in snapshot:
        return
    snapshot["seed_key"] = spec.seed_key
    invoice.seller_snapshot_json = snapshot


def create_invoice_via_service(session, invoice_service: InvoiceService, actor: AuthenticatedUser, spec: InvoiceSpec, contractor: ContractorORM) -> InvoiceORM:
    existing = find_existing_invoice_orm(session, spec, contractor)
    if existing is not None:
        ensure_invoice_seed_key(existing, spec)
        session.flush()
        if not existing.number_local:
            invoice_service.mark_as_ready(existing.id, actor)
            session.flush()
            refreshed = session.get(InvoiceORM, existing.id)
            if refreshed is None:
                raise RuntimeError(f"Nie udalo sie odswiezyc faktury {existing.id}.")
            return refreshed
        return existing

    payload = {
        "buyer_id": contractor.id,
        "issue_date": spec.issue_date,
        "sale_date": spec.issue_date,
        "currency": "PLN",
        "direction": spec.direction,
        "buyer_snapshot": {"seed_key": spec.seed_key} if spec.direction == "sale" else None,
        "seller_snapshot": {"seed_key": spec.seed_key} if spec.direction == "purchase" else None,
        "items": [
            {
                "name": f"Demo {spec.slug}",
                "quantity": Decimal("1.00"),
                "unit": "szt.",
                "unit_price_net": spec.net_amount,
                "vat_rate": spec.vat_rate,
            }
        ],
    }
    created = invoice_service.create_invoice(payload, actor)
    ready = invoice_service.mark_as_ready(created.id, actor)
    orm = session.get(InvoiceORM, ready.id)
    if orm is None:
        raise RuntimeError(f"Nie znaleziono utworzonej faktury {ready.id}.")
    ensure_invoice_seed_key(orm, spec)
    session.flush()
    return orm


def create_bank_transaction(session, tx_repo: BankTransactionRepository, actor: AuthenticatedUser, spec: TransactionSpec, contractor_name: str) -> BankTransactionORM:
    existing = tx_repo.get_by_external_id(spec.external_id)
    if existing is not None:
        return existing

    orm = BankTransactionORM(
        external_id=spec.external_id,
        transaction_date=spec.transaction_date,
        value_date=spec.transaction_date,
        amount=spec.amount,
        currency="PLN",
        counterparty_name=contractor_name,
        counterparty_account=None,
        title=spec.title,
        match_status="unmatched",
        remaining_amount=spec.amount,
        source_file=SOURCE_FILE,
        raw_row_json={"seed": "demo_april_2026", "slug": spec.slug},
        imported_by=UUID(actor.user_id),
    )
    return tx_repo.add(orm)


def allocation_exists(alloc_repo: PaymentAllocationRepository, transaction_id: UUID, invoice_id: UUID, amount: Decimal) -> bool:
    for allocation in alloc_repo.list_active_for_transaction(transaction_id):
        if allocation.invoice_id == invoice_id and allocation.is_reversed is False:
            return True
    return False


def allocate_payment(payment_service: PaymentService, alloc_repo: PaymentAllocationRepository, actor: AuthenticatedUser, transaction: BankTransactionORM, invoice: InvoiceORM, amount: Decimal) -> PaymentAllocationORM | None:
    if allocation_exists(alloc_repo, transaction.id, invoice.id, amount):
        return None
    remaining_amount = money(transaction.remaining_amount)
    requested_amount = money(amount)
    if remaining_amount <= Decimal("0"):
        return None
    if remaining_amount < requested_amount:
        return None
    return payment_service.allocate_manual(transaction.id, invoice.id, amount, actor)


def remaining_for_invoice(alloc_repo: PaymentAllocationRepository, invoice: InvoiceORM) -> Decimal:
    gross = money((invoice.totals_json or {}).get("total_gross", "0.00"))
    allocated = money(alloc_repo.sum_allocated_for_invoice(invoice.id))
    remaining = gross - allocated
    return remaining if remaining > Decimal("0.00") else Decimal("0.00")


def print_summary(alloc_repo: PaymentAllocationRepository, invoices: dict[str, InvoiceORM], transactions: dict[str, BankTransactionORM]) -> None:
    seeded_allocations = 0
    for transaction in transactions.values():
        seeded_allocations += sum(
            1
            for allocation in alloc_repo.list_active_for_transaction(transaction.id)
            if allocation.invoice_id in {invoice.id for invoice in invoices.values()}
        )

    receivables = Decimal("0.00")
    liabilities = Decimal("0.00")
    for invoice in invoices.values():
        remaining = remaining_for_invoice(alloc_repo, invoice)
        if invoice.direction == "sale":
            receivables += remaining
        else:
            liabilities += remaining

    total_invoices = len(invoices)
    total_transactions = len(transactions)
    total_allocations = seeded_allocations

    assert total_invoices == 8
    assert total_transactions == 5
    assert total_allocations == 5
    assert receivables > Decimal("0")
    assert liabilities > Decimal("0")

    print(
        {
            "invoices": total_invoices,
            "transactions": total_transactions,
            "allocations": total_allocations,
            "receivables": str(receivables.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "payables": str(liabilities.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }
    )


def run() -> None:
    with session_scope() as session:
        actor = build_actor(session)
        contractor_repo, _invoice_repo, tx_repo, alloc_repo, invoice_service, payment_service = build_services(session)

        contractors = ensure_contractors(session, contractor_repo)

        invoices: dict[str, InvoiceORM] = {}
        for spec in INVOICES:
            invoices[spec.slug] = create_invoice_via_service(
                session=session,
                invoice_service=invoice_service,
                actor=actor,
                spec=spec,
                contractor=contractors[spec.contractor_slug],
            )

        transactions: dict[str, BankTransactionORM] = {}
        for spec in TRANSACTIONS:
            invoice = invoices[spec.invoice_slug]
            contractor_name = (invoice.buyer_snapshot_json or {}).get("name") or "Kontrahent demo"
            transactions[spec.slug] = create_bank_transaction(
                session=session,
                tx_repo=tx_repo,
                actor=actor,
                spec=spec,
                contractor_name=contractor_name,
            )

        for transaction_slug, invoice_slug, amount in ALLOCATIONS:
            allocate_payment(
                payment_service=payment_service,
                alloc_repo=alloc_repo,
                actor=actor,
                transaction=transactions[transaction_slug],
                invoice=invoices[invoice_slug],
                amount=amount,
            )

        session.flush()
        print_summary(alloc_repo, invoices, transactions)


if __name__ == "__main__":
    run()