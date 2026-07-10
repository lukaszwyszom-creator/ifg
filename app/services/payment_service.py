"""Serwis modułu płatności.

Odpowiedzialności:
  - Import przelewów z CSV
  - Uruchomienie silnika scoringowego
  - Automatyczne i ręczne alokacje
  - Cofanie alokacji
  - Historia płatności faktury
  - Aktualizacja payment_status na fakturze
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.core.utils import to_uuid
from app.domain.enums import InvoicePaymentStatus, PaymentMatchMethod, PaymentMatchStatus
from app.persistence.models.bank_transaction import BankTransactionORM
from app.persistence.models.invoice import InvoiceORM
from app.persistence.models.payment_allocation import PaymentAllocationORM
from app.persistence.repositories.bank_transaction_repository import BankTransactionRepository
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.payment_allocation_repository import PaymentAllocationRepository
from app.services.audit_service import AuditService
from app.services.payment_csv_parser import (
    _CSV_COLUMN_ALIASES,
    _build_column_map,
    _parse_csv,
    _parse_date,
)
from app.services.payment_matcher import (
    AUTO_MATCH_THRESHOLD,
    MANUAL_REVIEW_THRESHOLD,
    InvoiceCandidate,
    PaymentMatcher,
    TransactionCandidate,
)

logger = logging.getLogger(__name__)

_INVOICE_CASH_EXTERNAL_PREFIX = "invoice-cash:"


# Re-eksport stałej i helperów CSV dla zachowania kompatybilności wstecznej.
# Logika znajduje się w ``app.services.payment_csv_parser``.
__all__ = [
    "PaymentService",
    "_CSV_COLUMN_ALIASES",
    "_build_column_map",
    "_parse_csv",
    "_parse_date",
]


class PaymentService:
    def __init__(
        self,
        session: Session,
        bank_transaction_repository: BankTransactionRepository,
        allocation_repository: PaymentAllocationRepository,
        invoice_repository: InvoiceRepository,
        audit_service: AuditService,
        matcher: PaymentMatcher | None = None,
    ) -> None:
        self._session = session
        self._tx_repo = bank_transaction_repository
        self._alloc_repo = allocation_repository
        self._inv_repo = invoice_repository
        self._audit = audit_service
        self._matcher = matcher or PaymentMatcher()

    # -------------------------------------------------------------------------
    # Import CSV
    # -------------------------------------------------------------------------

    def import_csv(
        self,
        csv_content: str,
        source_file: str | None,
        actor: AuthenticatedUser,
    ) -> dict[str, Any]:
        """Parsuje CSV, importuje nowe rekordy (deduplikacja via external_id), uruchamia matching."""
        rows = _parse_csv(csv_content)
        imported: list[BankTransactionORM] = []
        skipped = 0

        for row in rows:
            ext_id = row.get("external_id")
            if ext_id:
                existing = self._tx_repo.get_by_external_id(ext_id)
                if existing:
                    skipped += 1
                    continue

            try:
                tx_date = _parse_date(row["transaction_date"])
                amount = Decimal(str(row["amount"]).replace(",", ".").replace(" ", ""))
            except (KeyError, ValueError, InvalidOperation) as exc:
                logger.warning("Pominięto wiersz CSV (błąd parsowania): %s – %s", row, exc)
                skipped += 1
                continue

            orm = BankTransactionORM(
                id=uuid.uuid4(),
                external_id=ext_id or None,
                transaction_date=tx_date,
                value_date=_parse_date(row.get("value_date")) if row.get("value_date") else None,
                amount=amount,
                currency=row.get("currency", "PLN").strip().upper(),
                counterparty_name=row.get("counterparty_name"),
                counterparty_account=row.get("counterparty_account"),
                title=row.get("title"),
                match_status=PaymentMatchStatus.UNMATCHED.value,
                remaining_amount=amount,
                source_file=source_file,
                raw_row_json=row,
                imported_by=to_uuid(actor.user_id),
            )
            self._tx_repo.add(orm)
            imported.append(orm)
        self._session.flush()

        # Matching poza transakcją importu (każda transakcja w osobnej)
        auto_matched = 0
        manual_review = 0
        for tx_orm in imported:
            result = self._run_matching_for_orm(tx_orm, actor)
            if result == "auto":
                auto_matched += 1
            elif result == "manual_review":
                manual_review += 1

        return {
            "imported": len(imported),
            "skipped": skipped,
            "auto_matched": auto_matched,
            "manual_review": manual_review,
        }

    # -------------------------------------------------------------------------
    # Matching
    # -------------------------------------------------------------------------

    def run_matching_for_transaction(
        self, transaction_id: UUID, actor: AuthenticatedUser
    ) -> str:
        tx_orm = self._tx_repo.get_by_id(transaction_id)
        if tx_orm is None:
            raise NotFoundError("Transakcja nie została znaleziona.")
        return self._run_matching_for_orm(tx_orm, actor) or "no_match"

    def _run_matching_for_orm(
        self, tx_orm: BankTransactionORM, actor: AuthenticatedUser
    ) -> str | None:
        """Zwraca 'auto' | 'manual_review' | None."""
        tx_candidate = TransactionCandidate(
            transaction_id=tx_orm.id,
            amount=tx_orm.amount,
            title=tx_orm.title,
            counterparty_name=tx_orm.counterparty_name,
            counterparty_account=tx_orm.counterparty_account,
        )

        # Pobierz faktury gotowe do zaakceptowania / zaakceptowane z łączną kwotą
        invoices_orm = self._inv_repo.list_all()
        invoice_candidates = [
            InvoiceCandidate(
                invoice_id=inv.id,
                invoice_number=inv.number_local or "",
                gross_amount=Decimal(str(inv.totals_json.get("total_gross", 0))),
                buyer_name=inv.buyer_snapshot_json.get("name"),
                buyer_nip=inv.buyer_snapshot_json.get("nip"),
                seller_nip=inv.seller_snapshot_json.get("nip"),
            )
            for inv in invoices_orm
        ]

        best = self._matcher.best_auto(tx_candidate, invoice_candidates)
        if best and best.score >= AUTO_MATCH_THRESHOLD:
            self._do_allocate(
                tx_orm=tx_orm,
                invoice_id=best.invoice_id,
                amount=tx_orm.remaining_amount,
                method=PaymentMatchMethod.AUTO,
                score=best.score,
                reasons=best.reasons,
                actor=actor,
            )
            self._session.flush()
            return "auto"

        # Sprawdź czy są kandydaci na manual_review
        candidates = self._matcher.find_candidates(tx_candidate, invoice_candidates)
        has_manual = any(
            MANUAL_REVIEW_THRESHOLD <= c.score < AUTO_MATCH_THRESHOLD for c in candidates
        )
        if has_manual:
            self._tx_repo.update_match_status(
                tx_orm.id,
                PaymentMatchStatus.MANUAL_REVIEW,
                tx_orm.remaining_amount,
            )
            self._session.flush()
            return "manual_review"

        return None

    # -------------------------------------------------------------------------
    # Wpłata z formularza faktury (gotówka / wpłata ręczna)
    # -------------------------------------------------------------------------

    @staticmethod
    def _invoice_cash_external_id(invoice_id: UUID) -> str:
        return f"{_INVOICE_CASH_EXTERNAL_PREFIX}{invoice_id}"

    def get_invoice_form_payment_amount(self, invoice_id: UUID) -> Decimal:
        """Kwota wpłaty zapisana z formularza faktury (alokacja invoice-cash)."""
        _tx, alloc = self._find_invoice_form_allocation(invoice_id)
        if alloc is None:
            return Decimal("0")
        return Decimal(str(alloc.allocated_amount)).quantize(Decimal("0.01"))

    def _find_invoice_form_allocation(
        self, invoice_id: UUID
    ) -> tuple[BankTransactionORM | None, PaymentAllocationORM | None]:
        external_id = self._invoice_cash_external_id(invoice_id)
        tx = self._tx_repo.get_by_external_id(external_id)
        if tx is None:
            return None, None
        for alloc in self._alloc_repo.list_for_invoice(invoice_id):
            if alloc.transaction_id == tx.id:
                return tx, alloc
        return tx, None

    def set_invoice_form_payment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        actor: AuthenticatedUser,
        *,
        payment_date: date | None = None,
    ) -> PaymentAllocationORM | None:
        """Ustawia / aktualizuje / usuwa wpłatę z formularza faktury sprzedaży."""
        amount = Decimal(str(amount)).quantize(Decimal("0.01"))

        inv_orm = self._inv_repo.get_orm_by_id(invoice_id)
        if inv_orm is None:
            raise NotFoundError("Faktura nie została znaleziona.")

        if (inv_orm.direction or "sale").strip().lower() != "sale":
            raise ValueError("Wpłata z formularza jest dostępna tylko dla faktur sprzedaży.")

        gross = Decimal(str(inv_orm.totals_json.get("total_gross", 0)))
        tx, form_alloc = self._find_invoice_form_allocation(invoice_id)
        form_current = (
            Decimal(str(form_alloc.allocated_amount))
            if form_alloc is not None
            else Decimal("0")
        )
        total_allocated = self._alloc_repo.sum_allocated_for_invoice(invoice_id)
        other_allocated = total_allocated - form_current

        if amount > gross - other_allocated:
            raise ValueError(
                f"Kwota wpłaty ({amount}) przekracza pozostałą do zapłaty "
                f"({gross - other_allocated})."
            )

        if amount <= 0:
            if form_alloc is not None:
                self.reverse_allocation(form_alloc.id, actor)
            return None

        if form_alloc is not None and form_current == amount:
            return form_alloc

        if form_alloc is not None:
            self.reverse_allocation(form_alloc.id, actor)
            self._session.flush()
            tx, form_alloc = self._find_invoice_form_allocation(invoice_id)

        if tx is None:
            return self._create_invoice_form_payment(
                invoice_id=invoice_id,
                inv_orm=inv_orm,
                amount=amount,
                actor=actor,
                payment_date=payment_date,
            )

        tx_orm = self._tx_repo.get_by_id(tx.id)
        if tx_orm is None:
            raise NotFoundError("Transakcja wpłaty nie została znaleziona.")
        tx_orm.amount = amount
        tx_orm.remaining_amount = amount
        tx_orm.match_status = PaymentMatchStatus.UNMATCHED.value
        self._session.flush()

        alloc = self._do_allocate(
            tx_orm=tx_orm,
            invoice_id=invoice_id,
            amount=amount,
            method=PaymentMatchMethod.CASH,
            score=None,
            reasons=["invoice_form_payment"],
            actor=actor,
        )
        self._session.flush()
        return alloc

    def record_invoice_initial_payment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        actor: AuthenticatedUser,
        *,
        payment_date: date | None = None,
    ) -> PaymentAllocationORM | None:
        """Rejestruje wpłatę podaną przy tworzeniu faktury sprzedaży."""
        if amount <= 0:
            return None
        return self.set_invoice_form_payment(
            invoice_id, amount, actor, payment_date=payment_date
        )

    def _create_invoice_form_payment(
        self,
        *,
        invoice_id: UUID,
        inv_orm: InvoiceORM,
        amount: Decimal,
        actor: AuthenticatedUser,
        payment_date: date | None,
    ) -> PaymentAllocationORM:
        tx_date = payment_date or inv_orm.issue_date
        buyer_name = (inv_orm.buyer_snapshot_json or {}).get("name")
        invoice_number = inv_orm.number_local or str(invoice_id)

        tx_orm = BankTransactionORM(
            id=uuid.uuid4(),
            external_id=self._invoice_cash_external_id(invoice_id),
            transaction_date=tx_date,
            value_date=tx_date,
            amount=amount,
            currency=inv_orm.currency or "PLN",
            counterparty_name=buyer_name,
            title=f"Wpłata przy wystawieniu faktury {invoice_number}",
            match_status=PaymentMatchStatus.UNMATCHED.value,
            remaining_amount=amount,
            source_file="invoice_initial_payment",
            imported_by=to_uuid(actor.user_id),
            imported_at=datetime.now(UTC),
        )
        self._tx_repo.add(tx_orm)

        alloc = self._do_allocate(
            tx_orm=tx_orm,
            invoice_id=invoice_id,
            amount=amount,
            method=PaymentMatchMethod.CASH,
            score=None,
            reasons=["invoice_initial_payment"],
            actor=actor,
        )
        self._session.flush()
        return alloc

    # -------------------------------------------------------------------------
    # Ręczna alokacja
    # -------------------------------------------------------------------------

    def allocate_manual(
        self,
        transaction_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
        actor: AuthenticatedUser,
    ) -> PaymentAllocationORM:
        tx_orm = self._tx_repo.get_by_id(transaction_id)
        if tx_orm is None:
            raise NotFoundError("Transakcja nie została znaleziona.")
        inv_orm = self._inv_repo.get_orm_by_id(invoice_id)
        if inv_orm is None:
            raise NotFoundError("Faktura nie została znaleziona.")

        if amount > tx_orm.remaining_amount:
            raise ValueError(
                f"Kwota alokacji ({amount}) przekracza pozostałe saldo transakcji "
                f"({tx_orm.remaining_amount})."
            )
        if amount <= 0:
            raise ValueError("Kwota alokacji musi być dodatnia.")

        alloc = self._do_allocate(
            tx_orm=tx_orm,
            invoice_id=invoice_id,
            amount=amount,
            method=PaymentMatchMethod.MANUAL,
            score=None,
            reasons=[],
            actor=actor,
        )
        self._session.flush()
        return alloc

    # -------------------------------------------------------------------------
    # Cofnięcie alokacji
    # -------------------------------------------------------------------------

    def reverse_allocation(
        self, allocation_id: UUID, actor: AuthenticatedUser
    ) -> None:
        alloc = self._alloc_repo.get_by_id(allocation_id)
        if alloc is None:
            raise NotFoundError("Alokacja nie została znaleziona.")

        before_alloc = {"is_reversed": alloc.is_reversed}
        self._alloc_repo.reverse(allocation_id, actor.user_id)

        # Zaktualizuj remaining_amount + match_status transakcji
        tx_orm = self._tx_repo.get_by_id(alloc.transaction_id)
        if tx_orm:
            allocated = self._alloc_repo.sum_allocated_for_transaction(tx_orm.id)
            remaining = tx_orm.amount - allocated
            match_status = self._compute_tx_match_status(tx_orm.amount, remaining)
            self._tx_repo.update_match_status(tx_orm.id, match_status, remaining)

        # Zaktualizuj payment_status faktury
        inv_orm = self._inv_repo.get_orm_by_id(alloc.invoice_id)
        if inv_orm:
            self._refresh_invoice_payment_status(inv_orm)

        self._audit.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="payment_allocation_reversed",
            entity_type="payment_allocation",
            entity_id=str(allocation_id),
            before=before_alloc,
            after={"is_reversed": True},
        )
        self._session.flush()

    # -------------------------------------------------------------------------
    # Historia płatności faktury
    # -------------------------------------------------------------------------

    def get_invoice_payment_history(
        self, invoice_id: UUID
    ) -> list[PaymentAllocationORM]:
        orm = self._inv_repo.get_orm_by_id(invoice_id)
        if orm is None:
            raise NotFoundError("Faktura nie została znaleziona.")
        return self._alloc_repo.list_for_invoice_all(invoice_id)

    # -------------------------------------------------------------------------
    # Listowanie
    # -------------------------------------------------------------------------

    def list_transactions(
        self,
        page: int = 1,
        size: int = 50,
        match_status: str | None = None,
    ) -> tuple[list[BankTransactionORM], int]:
        if match_status:
            return self._tx_repo.list_unmatched_paginated(page, size, match_status)
        return self._tx_repo.list_all_paginated(page, size)

    def get_settlement_summary(
        self,
        side: str | None = None,
        month: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Read-only podsumowanie rozrachunków dla sprzedaży/zakupu."""
        normalized_side = (side or "all").strip().lower()
        allowed_sides = {"all", "sales", "purchase"}
        if normalized_side not in allowed_sides:
            raise ValueError("Parametr 'side' musi mieć wartość: sales|purchase|all.")

        month_start: date | None = None
        month_end: date | None = None
        if month:
            try:
                month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
            except ValueError as exc:
                raise ValueError("Parametr 'month' musi mieć format YYYY-MM.") from exc

            if month_start.month == 12:
                month_end = date(month_start.year + 1, 1, 1)
            else:
                month_end = date(month_start.year, month_start.month + 1, 1)

        direction = None
        if normalized_side == "sales":
            direction = "sale"
        elif normalized_side == "purchase":
            direction = "purchase"

        rows = self._alloc_repo.list_open_invoices_with_paid_amount(
            direction=direction,
            month_start=month_start,
            month_end=month_end,
        )

        debtors: list[dict[str, Any]] = []
        creditors: list[dict[str, Any]] = []

        for row in rows:
            remaining_amount = row.gross_total - row.paid_amount
            if remaining_amount <= Decimal("0"):
                continue

            if row.direction == "sale":
                target = debtors
            elif row.direction == "purchase":
                target = creditors
            else:
                continue

            target.append(
                {
                    "invoice_id": row.invoice_id,
                    "number_local": row.number_local,
                    "ksef_reference_number": row.ksef_reference_number,
                    "contractor_name": row.contractor_name,
                    "currency": row.currency,
                    "issue_date": row.issue_date,
                    "due_date": row.due_date,
                    "gross_total": row.gross_total,
                    "paid_amount": row.paid_amount,
                    "remaining_amount": remaining_amount,
                    "payment_status": row.payment_status,
                    "invoice_type": row.invoice_type,
                    "side": row.direction,
                }
            )

        return {"debtors": debtors, "creditors": creditors}

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _do_allocate(
        self,
        tx_orm: BankTransactionORM,
        invoice_id: UUID,
        amount: Decimal,
        method: PaymentMatchMethod,
        score: int | None,
        reasons: list[str],
        actor: AuthenticatedUser,
    ) -> PaymentAllocationORM:
        alloc = PaymentAllocationORM(
            id=uuid.uuid4(),
            transaction_id=tx_orm.id,
            invoice_id=invoice_id,
            allocated_amount=amount,
            match_method=method.value,
            match_score=score,
            match_reasons_json=reasons,
            is_reversed=False,
            created_by=to_uuid(actor.user_id),
        )
        self._alloc_repo.add(alloc)

        # Zaktualizuj remaining + match_status na transakcji
        allocated_total = self._alloc_repo.sum_allocated_for_transaction(tx_orm.id)
        remaining = tx_orm.amount - allocated_total
        match_status = self._compute_tx_match_status(tx_orm.amount, remaining)
        self._tx_repo.update_match_status(tx_orm.id, match_status, remaining)

        # Zaktualizuj payment_status faktury
        inv_orm = self._inv_repo.get_orm_by_id(invoice_id)
        if inv_orm:
            self._refresh_invoice_payment_status(inv_orm)

        self._audit.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="payment_allocated",
            entity_type="bank_transaction",
            entity_id=str(tx_orm.id),
            before={},
            after={
                "invoice_id": str(invoice_id),
                "amount": str(amount),
                "method": method.value,
                "score": score,
            },
        )
        return alloc

    def _refresh_invoice_payment_status(self, inv_orm: InvoiceORM) -> None:
        gross = Decimal(str(inv_orm.totals_json.get("total_gross", 0)))
        allocated = self._alloc_repo.sum_allocated_for_invoice(inv_orm.id)
        if gross <= 0:
            new_status = InvoicePaymentStatus.UNPAID
        elif allocated >= gross:
            new_status = InvoicePaymentStatus.PAID
        elif allocated > 0:
            new_status = InvoicePaymentStatus.PARTIALLY_PAID
        else:
            new_status = InvoicePaymentStatus.UNPAID
        inv_orm.payment_status = new_status.value
        self._session.flush()

    @staticmethod
    def _compute_tx_match_status(
        amount: Decimal, remaining: Decimal
    ) -> PaymentMatchStatus:
        if remaining <= 0:
            return PaymentMatchStatus.MATCHED
        if remaining < amount:
            return PaymentMatchStatus.PARTIAL
        return PaymentMatchStatus.UNMATCHED
