from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.core.utils import to_uuid
from app.domain.enums import InvoiceStatus
from app.domain.exceptions import InvalidInvoiceError, InvalidStatusTransitionError
from app.domain.models.invoice import Invoice, calculate_overdue_days
from app.persistence.mappers.invoice_mapper import InvoiceMapper
from app.persistence.repositories.contractor_override_repository import (
    ContractorOverrideRepository,
)
from app.persistence.repositories.contractor_repository import ContractorRepository
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.payment_allocation_repository import (
    PaymentAllocationRepository,
)
from app.integrations.nbp.client import NbpRateClient, NbpRateError
from app.services.audit_service import AuditService
from app.services.invoice_number_policy import InvoiceNumberPolicy
from app.services.invoice_totals import InvoiceTotalsCalculator
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")


class InvoiceService:
    MAX_RETRIES = 3

    def __init__(
        self,
        session: Session,
        invoice_repository: InvoiceRepository,
        contractor_repository: ContractorRepository,
        contractor_override_repository: ContractorOverrideRepository,
        audit_service: AuditService,
        stock_service: StockService | None = None,
        payment_allocation_repository: PaymentAllocationRepository | None = None,
    ) -> None:
        self.session = session
        self.invoice_repository = invoice_repository
        self.contractor_repository = contractor_repository
        self.contractor_override_repository = contractor_override_repository
        self.audit_service = audit_service
        self.stock_service = stock_service
        self.payment_allocation_repository = payment_allocation_repository

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    @staticmethod
    def is_invoice_editable(status: InvoiceStatus | str) -> bool:
        """
        Sprawdza, czy faktura w danym statusie może być edytowana.

        Edytowalne:
        - READY_FOR_SUBMISSION (gotowa do wysyłki)
        - REJECTED (odrzucona, wymaga poprawy)

        Nieedytowalne:
        - SENDING (analiza w KSeF, tylko podgląd)
        - ACCEPTED (zaakceptowana, tylko podgląd)
        """
        if isinstance(status, str):
            status = InvoiceStatus(status)

        return status in (InvoiceStatus.READY_FOR_SUBMISSION, InvoiceStatus.REJECTED)

    def create_invoice(self, data: dict, actor: AuthenticatedUser) -> Invoice:
        buyer_id: UUID | None = data.get("buyer_id")
        if buyer_id is None:
            raise InvalidInvoiceError("Nabywca (buyer_id) jest wymagany.")

        raw_items: list[dict] = data.get("items", [])
        if not raw_items:
            raise InvalidInvoiceError(
                "Faktura musi zawierać co najmniej jedną pozycję."
            )

        issue_date = data["issue_date"]
        sale_date = data["sale_date"]
        delivery_date: date | None = data.get("delivery_date")

        if sale_date > issue_date:
            raise InvalidInvoiceError(
                "Data sprzedaży nie może być późniejsza niż data wystawienia."
            )

        due_date: date | None = data.get("due_date")
        if due_date is None:
            due_date = issue_date + timedelta(days=14)

        buyer_snapshot = self._resolve_buyer_snapshot(buyer_id)
        seller_snapshot = self._build_seller_snapshot()
        items = InvoiceTotalsCalculator.build_items(raw_items)
        total_net, total_vat, total_gross = InvoiceTotalsCalculator.calculate_totals(items)

        currency = data.get("currency", "PLN")
        exchange_rate: Decimal | None = data.get("exchange_rate")
        exchange_rate_date: date | None = data.get("exchange_rate_date")

        if currency != "PLN" and exchange_rate is None:
            nbp_date = exchange_rate_date or (issue_date - date.resolution)
            try:
                exchange_rate = NbpRateClient().get_mid_rate(currency, nbp_date)
                exchange_rate_date = nbp_date
            except NbpRateError as exc:
                logger.warning("Nie udało się pobrać kursu NBP dla %s: %s", currency, exc)

        now = datetime.now(UTC)

        invoice = Invoice(
            id=uuid4(),
            number_local=None,
            status=InvoiceStatus.READY_FOR_SUBMISSION,
            direction=data.get("direction", "sale"),
            issue_date=issue_date,
            sale_date=sale_date,
            delivery_date=delivery_date,
            due_date=due_date,
            currency=currency,
            exchange_rate=exchange_rate,
            exchange_rate_date=exchange_rate_date,
            seller_snapshot=seller_snapshot,
            buyer_snapshot=buyer_snapshot,
            items=items,
            total_net=total_net,
            total_vat=total_vat,
            total_gross=total_gross,
            created_by=to_uuid(actor.user_id),
            created_at=now,
            updated_at=now,
        )

        saved = self.invoice_repository.add(invoice)
        self.session.flush()

        self.audit_service.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="invoice.created",
            entity_type="invoice",
            entity_id=str(saved.id),
            after={
                "status": saved.status.value,
                "total_gross": str(saved.total_gross),
            },
        )

        if self.stock_service is not None:
            self.stock_service.handle_invoice_created(
                invoice_id=saved.id,
                direction=saved.direction,
                items=[
                    {"product_id": item.product_id, "quantity": item.quantity}
                    for item in saved.items
                    if hasattr(item, "product_id")
                ],
            )

        return saved

    def get_invoice(self, invoice_id: UUID) -> Invoice:
        invoice = self.invoice_repository.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError(f"Nie znaleziono faktury {invoice_id}.")
        return invoice

    def update_invoice(
        self, invoice_id: UUID, data: dict, actor: AuthenticatedUser
    ) -> Invoice:
        invoice = self.invoice_repository.lock_for_update(invoice_id)
        if invoice is None:
            raise NotFoundError(f"Nie znaleziono faktury {invoice_id}.")

        # Sprawdzenie edytowalności na podstawie statusu
        if not self.is_invoice_editable(invoice.status):
            status_label = {
                InvoiceStatus.SENDING: "Analiza",
                InvoiceStatus.ACCEPTED: "Zaakceptowana",
            }.get(invoice.status, invoice.status.value)
            raise InvalidStatusTransitionError(
                f"Faktura w statusie '{status_label}' nie może być edytowana."
            )

        buyer_id: UUID | None = data.get("buyer_id")
        if buyer_id is None:
            raise InvalidInvoiceError("Nabywca (buyer_id) jest wymagany.")

        raw_items: list[dict] = data.get("items", [])
        if not raw_items:
            raise InvalidInvoiceError(
                "Faktura musi zawierać co najmniej jedną pozycję."
            )

        issue_date = data["issue_date"]
        sale_date = data["sale_date"]
        delivery_date: date | None = data.get("delivery_date")

        if sale_date > issue_date:
            raise InvalidInvoiceError(
                "Data sprzedaży nie może być późniejsza niż data wystawienia."
            )

        buyer_snapshot = self._resolve_buyer_snapshot(buyer_id)
        items = InvoiceTotalsCalculator.build_items(raw_items)
        total_net, total_vat, total_gross = InvoiceTotalsCalculator.calculate_totals(items)

        invoice.buyer_snapshot = buyer_snapshot
        invoice.issue_date = issue_date
        invoice.sale_date = sale_date
        invoice.delivery_date = delivery_date
        if "due_date" in data:
            invoice.due_date = data.get("due_date")
        invoice.currency = data.get("currency", invoice.currency)
        invoice.items = items
        invoice.total_net = total_net
        invoice.total_vat = total_vat
        invoice.total_gross = total_gross
        invoice.updated_at = datetime.now(UTC)

        updated = self.invoice_repository.update(invoice_id, invoice)
        self.session.flush()

        self.audit_service.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="invoice.updated",
            entity_type="invoice",
            entity_id=str(invoice_id),
            after={
                "status": updated.status.value,
                "number_local": updated.number_local,
                "issue_date": str(updated.issue_date),
            },
        )

        return updated

    def list_invoices(
        self,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        issue_date_from: date | None = None,
        issue_date_to: date | None = None,
        issue_date_before: date | None = None,
        number_filter: str | None = None,
        direction: str | None = None,
        view: str | None = None,
    ) -> tuple[list[Invoice], int]:
        if issue_date_to is not None and issue_date_before is not None:
            raise InvalidInvoiceError(
                "Nie można używać jednocześnie issue_date_to i issue_date_before."
            )

        payment_status_in: tuple[str, ...] | None = None
        order_by_due_date = False
        if view == "open":
            # Widok operacyjny: wszystkie nieuregulowane faktury, niezależnie od miesiąca.
            # Świadomie ignorujemy filtry dat — ten widok ma pokazać ogon zaległości.
            payment_status_in = ("unpaid", "partially_paid")
            order_by_due_date = True
            issue_date_from = None
            issue_date_to = None
            issue_date_before = None
        elif view is not None and view != "month":
            raise InvalidInvoiceError(
                f"Nieobsługiwana wartość parametru 'view': {view!r}. "
                "Dozwolone: 'open', 'month'."
            )

        return self.invoice_repository.list_paginated(
            status=status,
            page=page,
            size=size,
            issue_date_from=issue_date_from,
            issue_date_to=issue_date_to,
            issue_date_before=issue_date_before,
            number_filter=number_filter,
            direction=direction,
            payment_status_in=payment_status_in,
            order_by_due_date=order_by_due_date,
        )

    def compute_remaining_amounts(
        self, invoices: list[Invoice]
    ) -> dict[UUID, Decimal]:
        """Zwraca remaining_amount = total_gross - sum(active allocations) per faktura.

        Wynik jest read-only (nie zapisujemy w DB). Dla statusu 'paid' wynik = 0,
        dla 'unpaid' bez alokacji = total_gross, dla 'partially_paid' = różnica.
        Gdy repo alokacji nie zostało wstrzyknięte, zwraca dict pusty (fallback
        po stronie warstwy schematu: brak danych = None w odpowiedzi).

        Optymalizacja: jeden SELECT … GROUP BY zamiast N+1 (batch po invoice_id).
        """
        if self.payment_allocation_repository is None or not invoices:
            return {}
        invoice_ids = [inv.id for inv in invoices]
        allocated_map = self.payment_allocation_repository.sum_allocated_for_invoices(
            invoice_ids
        )
        result: dict[UUID, Decimal] = {}
        for inv in invoices:
            allocated = allocated_map.get(inv.id, Decimal("0"))
            remaining = (Decimal(inv.total_gross) - allocated).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if remaining < Decimal("0"):
                remaining = Decimal("0")
            result[inv.id] = remaining
        return result

    def compute_open_summary(
        self,
        invoices: list[Invoice],
        remaining_map: dict[UUID, Decimal],
    ) -> dict[str, Decimal]:
        """Agreguje sumy dla widoku 'Otwarte' na bazie już policzonych remaining_amount.

        Bez dodatkowych zapytań do DB — operuje na danych przekazanych z routera.
        sale → receivables (do odzyskania), purchase → payables (do zapłaty).
        """
        two_places = Decimal("0.01")
        receivables = Decimal("0")
        payables = Decimal("0")
        overdue_0_30 = Decimal("0")
        overdue_30_60 = Decimal("0")
        overdue_60_plus = Decimal("0")
        for inv in invoices:
            remaining_raw = remaining_map.get(inv.id, Decimal("0"))
            remaining = (
                remaining_raw
                if isinstance(remaining_raw, Decimal)
                else Decimal(str(remaining_raw))
            )
            if inv.direction == "purchase":
                payables += remaining
            else:
                receivables += remaining

            overdue_days = calculate_overdue_days(inv.due_date)
            if overdue_days is None:
                continue
            if overdue_days == 0:
                continue
            if 1 <= overdue_days <= 30:
                overdue_0_30 += remaining
            elif 31 <= overdue_days <= 60:
                overdue_30_60 += remaining
            elif overdue_days >= 61:
                overdue_60_plus += remaining
        return {
            "total_receivables": receivables.quantize(
                two_places, rounding=ROUND_HALF_UP
            ),
            "total_payables": payables.quantize(
                two_places, rounding=ROUND_HALF_UP
            ),
            "overdue_0_30": overdue_0_30.quantize(
                two_places, rounding=ROUND_HALF_UP
            ),
            "overdue_30_60": overdue_30_60.quantize(
                two_places, rounding=ROUND_HALF_UP
            ),
            "overdue_60_plus": overdue_60_plus.quantize(
                two_places, rounding=ROUND_HALF_UP
            ),
        }

    # Po migracji usuwającej status draft mark-ready jest świadomie idempotentne:
    # dla READY_FOR_SUBMISSION tylko uzupełnia number_local (jeśli brak),
    # a dla statusów końcowych/analitycznych pozostaje blokowane (409).
    def mark_as_ready(
        self, invoice_id: UUID, actor: AuthenticatedUser
    ) -> Invoice:
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                invoice = self.invoice_repository.lock_for_update(invoice_id)
                if invoice is None:
                    raise NotFoundError(f"Faktura {invoice_id} nie istnieje.")

                if invoice.status != InvoiceStatus.READY_FOR_SUBMISSION:
                    raise InvalidStatusTransitionError(
                        "Nie można oznaczyć faktury jako gotowej dla statusu "
                        f"'{invoice.status.value}'."
                    )

                if invoice.number_local:
                    logger.info(
                        "mark-ready idempotent hit: invoice_id=%s number=%s",
                        invoice_id,
                        invoice.number_local,
                    )
                    return invoice

                year = invoice.issue_date.year
                month = invoice.issue_date.month

                seq = self.invoice_repository.get_next_sequence_number(year, month)
                number = InvoiceNumberPolicy.generate(year, month, seq)

                if self.invoice_repository.exists_by_number(number):
                    raise IntegrityError(
                        statement=None,
                        params=None,
                        orig=Exception(f"Duplikat numeru faktury: {number}"),
                    )

                invoice.number_local = number
                invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
                invoice.updated_at = datetime.now(UTC)

                updated = self.invoice_repository.update(invoice_id, invoice)
                self.session.flush()

                self.audit_service.record(
                    actor_user_id=actor.user_id,
                    actor_role=actor.role,
                    event_type="invoice.marked_ready",
                    entity_type="invoice",
                    entity_id=str(invoice_id),
                    after={
                        "status": updated.status.value,
                        "number_local": updated.number_local,
                    },
                )

                logger.info(
                    "Faktura oznaczona jako gotowa: invoice_id=%s number=%s",
                    invoice_id,
                    updated.number_local,
                )

                return updated

            except (InvalidStatusTransitionError, NotFoundError, ValueError):
                raise

            except (IntegrityError, OperationalError):
                self.session.rollback()

                if attempt >= self.MAX_RETRIES:
                    logger.exception(
                        "Nie udało się oznaczyć faktury jako gotowej: invoice_id=%s",
                        invoice_id,
                    )
                    raise

                logger.warning(
                    "Retry mark_as_ready: attempt=%s/%s invoice_id=%s",
                    attempt,
                    self.MAX_RETRIES,
                    invoice_id,
                )

        raise RuntimeError(
            f"Nie udało się oznaczyć faktury jako gotowej: {invoice_id}"
        )

    # -------------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------------

    def _resolve_buyer_snapshot(self, buyer_id: UUID) -> dict:
        contractor = self.contractor_repository.get_by_id(buyer_id)
        if contractor is None:
            raise NotFoundError(f"Nie znaleziono kontrahenta {buyer_id}.")

        override = (
            self.contractor_override_repository.get_active_by_contractor_id(buyer_id)
        )
        return InvoiceMapper.build_contractor_snapshot(contractor, override)

    @staticmethod
    def _build_seller_snapshot() -> dict:
        return {
            "nip": settings.seller_nip,
            "name": settings.seller_name,
            "street": settings.seller_street,
            "building_no": settings.seller_building_no,
            "apartment_no": settings.seller_apartment_no,
            "postal_code": settings.seller_postal_code,
            "city": settings.seller_city,
            "country": settings.seller_country,
        }
