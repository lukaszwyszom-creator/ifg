from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func as sa_func, select
from sqlalchemy.orm import Session, joinedload

from app.persistence.models.invoice import InvoiceORM
from app.persistence.models.payment_allocation import PaymentAllocationORM


@dataclass(slots=True)
class SettlementOpenInvoiceRow:
    invoice_id: UUID
    number_local: str | None
    contractor_name: str | None
    issue_date: date
    gross_total: Decimal
    paid_amount: Decimal
    payment_status: str
    invoice_type: str | None
    direction: str


class PaymentAllocationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, orm: PaymentAllocationORM) -> PaymentAllocationORM:
        self._session.add(orm)
        self._session.flush()
        return orm

    def reverse(self, allocation_id: UUID, reversed_by: str | UUID | None) -> PaymentAllocationORM:
        orm = self._get_orm(allocation_id)
        if orm is None:
            raise ValueError(f"Nie znaleziono alokacji {allocation_id}.")
        if orm.is_reversed:
            raise ValueError("Alokacja już została cofnięta.")
        orm.is_reversed = True
        orm.reversed_at = datetime.now(UTC)
        orm.reversed_by = uuid.UUID(reversed_by) if isinstance(reversed_by, str) else reversed_by
        self._session.flush()
        return orm

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, allocation_id: UUID) -> PaymentAllocationORM | None:
        return self._get_orm(allocation_id)

    def list_for_invoice(self, invoice_id: UUID) -> list[PaymentAllocationORM]:
        """Zwraca aktywne (niercofnięte) alokacje dla faktury wraz z transakcją."""
        stmt = (
            select(PaymentAllocationORM)
            .options(joinedload(PaymentAllocationORM.transaction))
            .where(
                PaymentAllocationORM.invoice_id == invoice_id,
                PaymentAllocationORM.is_reversed.is_(False),
            )
            .order_by(PaymentAllocationORM.created_at.desc())
        )
        return list(self._session.execute(stmt).unique().scalars().all())

    def list_for_invoice_all(self, invoice_id: UUID) -> list[PaymentAllocationORM]:
        """Zwraca wszystkie alokacje (łącznie z cofniętymi) — historia."""
        stmt = (
            select(PaymentAllocationORM)
            .options(joinedload(PaymentAllocationORM.transaction))
            .where(PaymentAllocationORM.invoice_id == invoice_id)
            .order_by(PaymentAllocationORM.created_at.desc())
        )
        return list(self._session.execute(stmt).unique().scalars().all())

    def list_active_for_transaction(self, transaction_id: UUID) -> list[PaymentAllocationORM]:
        stmt = (
            select(PaymentAllocationORM)
            .where(
                PaymentAllocationORM.transaction_id == transaction_id,
                PaymentAllocationORM.is_reversed.is_(False),
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    def sum_allocated_for_invoice(self, invoice_id: UUID) -> Decimal:
        stmt = (
            select(sa_func.coalesce(sa_func.sum(PaymentAllocationORM.allocated_amount), 0))
            .where(
                PaymentAllocationORM.invoice_id == invoice_id,
                PaymentAllocationORM.is_reversed.is_(False),
            )
        )
        return Decimal(str(self._session.execute(stmt).scalar_one()))

    def sum_allocated_for_transaction(self, transaction_id: UUID) -> Decimal:
        stmt = (
            select(sa_func.coalesce(sa_func.sum(PaymentAllocationORM.allocated_amount), 0))
            .where(
                PaymentAllocationORM.transaction_id == transaction_id,
                PaymentAllocationORM.is_reversed.is_(False),
            )
        )
        return Decimal(str(self._session.execute(stmt).scalar_one()))

    def list_open_invoices_with_paid_amount(
        self,
        *,
        direction: str | None = None,
        month_start: date | None = None,
        month_end: date | None = None,
    ) -> list[SettlementOpenInvoiceRow]:
        """Zwraca read-model rozrachunków dla faktur unpaid/partially_paid."""
        paid_amount = sa_func.coalesce(sa_func.sum(PaymentAllocationORM.allocated_amount), 0)
        stmt = (
            select(
                InvoiceORM.id,
                InvoiceORM.number_local,
                InvoiceORM.buyer_snapshot_json,
                InvoiceORM.seller_snapshot_json,
                InvoiceORM.issue_date,
                InvoiceORM.totals_json,
                InvoiceORM.payment_status,
                InvoiceORM.invoice_type,
                InvoiceORM.direction,
                paid_amount.label("paid_amount"),
            )
            .outerjoin(
                PaymentAllocationORM,
                and_(
                    PaymentAllocationORM.invoice_id == InvoiceORM.id,
                    PaymentAllocationORM.is_reversed.is_(False),
                ),
            )
            .where(InvoiceORM.payment_status.in_(["unpaid", "partially_paid"]))
            .group_by(
                InvoiceORM.id,
                InvoiceORM.number_local,
                InvoiceORM.buyer_snapshot_json,
                InvoiceORM.seller_snapshot_json,
                InvoiceORM.issue_date,
                InvoiceORM.totals_json,
                InvoiceORM.payment_status,
                InvoiceORM.invoice_type,
                InvoiceORM.direction,
            )
            .order_by(InvoiceORM.issue_date.desc(), InvoiceORM.created_at.desc())
        )

        if direction is not None:
            stmt = stmt.where(InvoiceORM.direction == direction)
        if month_start is not None:
            stmt = stmt.where(InvoiceORM.issue_date >= month_start)
        if month_end is not None:
            stmt = stmt.where(InvoiceORM.issue_date < month_end)

        rows = self._session.execute(stmt).all()

        result: list[SettlementOpenInvoiceRow] = []
        for (
            invoice_id,
            number_local,
            buyer_snapshot_json,
            seller_snapshot_json,
            issue_date,
            totals_json,
            payment_status,
            invoice_type,
            direction_value,
            sum_paid,
        ) in rows:
            normalized_direction = (direction_value or "sale").strip().lower()
            buyer_name = (buyer_snapshot_json or {}).get("name")
            seller_name = (seller_snapshot_json or {}).get("name")
            contractor_name = buyer_name if normalized_direction == "sale" else seller_name

            result.append(
                SettlementOpenInvoiceRow(
                    invoice_id=invoice_id,
                    number_local=number_local,
                    contractor_name=contractor_name,
                    issue_date=issue_date,
                    gross_total=Decimal(str((totals_json or {}).get("total_gross", 0))),
                    paid_amount=Decimal(str(sum_paid)),
                    payment_status=payment_status,
                    invoice_type=invoice_type,
                    direction=normalized_direction,
                )
            )

        return result

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_orm(self, allocation_id: UUID) -> PaymentAllocationORM | None:
        stmt = select(PaymentAllocationORM).where(PaymentAllocationORM.id == allocation_id)
        return self._session.execute(stmt).scalar_one_or_none()
