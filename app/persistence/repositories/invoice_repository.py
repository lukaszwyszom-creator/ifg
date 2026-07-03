from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.domain.models.invoice import Invoice
from app.persistence.mappers.invoice_mapper import InvoiceMapper
from app.persistence.models.invoice import InvoiceORM


class InvoiceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, invoice_id: UUID) -> Invoice | None:
        orm = self.session.get(InvoiceORM, invoice_id)
        if orm is None:
            return None
        return InvoiceMapper.to_domain(orm)

    def get_orm_by_id(self, invoice_id: UUID) -> InvoiceORM | None:
        return self.session.get(InvoiceORM, invoice_id)

    def lock_for_update(self, invoice_id: UUID) -> Invoice | None:
        """Pobiera fakturę z blokadą FOR UPDATE (tylko PostgreSQL).
        W SQLite działa bez blokady.
        """
        try:
            stmt = (
                select(InvoiceORM)
                .where(InvoiceORM.id == invoice_id)
                .with_for_update()
            )
            orm = self.session.execute(stmt).scalar_one_or_none()
        except Exception:
            # SQLite nie obsługuje FOR UPDATE — fallback
            orm = self.session.get(InvoiceORM, invoice_id)

        if orm is None:
            return None
        return InvoiceMapper.to_domain(orm)

    def add(self, invoice: Invoice, source_system: str | None = None) -> Invoice:
        orm = InvoiceMapper.to_orm(invoice)
        if source_system:
            payload = dict(orm.ksef_payload_json or {})
            payload["source_system"] = source_system
            orm.ksef_payload_json = payload
        self.session.add(orm)
        self.session.flush()
        return InvoiceMapper.to_domain(orm)

    def update(self, invoice_id: UUID, invoice: Invoice) -> Invoice:
        orm = self.session.get(InvoiceORM, invoice_id)
        if orm is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"Nie znaleziono faktury {invoice_id}.")
        InvoiceMapper.update_orm(orm, invoice)
        self.session.flush()
        return InvoiceMapper.to_domain(orm)

    def list_paginated(
        self,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        issue_date_from: date | None = None,
        issue_date_to: date | None = None,
        issue_date_before: date | None = None,
        number_filter: str | None = None,
        direction: str | None = None,
        payment_status_in: tuple[str, ...] | None = None,
        order_by_due_date: bool = False,
    ) -> tuple[list[Invoice], int]:
        base_stmt = select(InvoiceORM)

        if status is not None:
            base_stmt = base_stmt.where(InvoiceORM.status == status)
        if issue_date_from is not None:
            base_stmt = base_stmt.where(InvoiceORM.issue_date >= issue_date_from)
        if issue_date_to is not None:
            base_stmt = base_stmt.where(InvoiceORM.issue_date <= issue_date_to)
        if issue_date_before is not None:
            base_stmt = base_stmt.where(InvoiceORM.issue_date < issue_date_before)
        if payment_status_in:
            base_stmt = base_stmt.where(InvoiceORM.payment_status.in_(payment_status_in))
        if number_filter is not None:
            normalized_filter = number_filter.strip()
            if normalized_filter:
                pattern = f"%{normalized_filter}%"
                base_stmt = base_stmt.where(
                    or_(
                        InvoiceORM.number_local.ilike(pattern),
                        InvoiceORM.buyer_snapshot_json["nip"].astext.ilike(pattern),
                        InvoiceORM.buyer_snapshot_json["name"].astext.ilike(pattern),
                        InvoiceORM.seller_snapshot_json["nip"].astext.ilike(pattern),
                        InvoiceORM.seller_snapshot_json["name"].astext.ilike(pattern),
                        cast(InvoiceORM.buyer_snapshot_json, String).ilike(pattern),
                        cast(InvoiceORM.seller_snapshot_json, String).ilike(pattern),
                    )
                )
        if direction is not None:
            normalized_direction = direction.strip().lower()
            if normalized_direction:
                base_stmt = base_stmt.where(func.lower(InvoiceORM.direction) == normalized_direction)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.session.execute(count_stmt).scalar_one()

        if order_by_due_date:
            # ORDER BY due_date ASC NULLS LAST, issue_date ASC
            order_clause = (
                InvoiceORM.due_date.asc().nulls_last(),
                InvoiceORM.issue_date.asc(),
            )
        else:
            order_clause = (InvoiceORM.created_at.desc(),)

        data_stmt = (
            base_stmt
            .order_by(*order_clause)
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = list(self.session.execute(data_stmt).scalars())
        return [InvoiceMapper.to_domain(orm) for orm in rows], total

    def exists_by_number(self, number_local: str) -> bool:
        stmt = select(
            select(InvoiceORM).where(InvoiceORM.number_local == number_local).exists()
        )
        return bool(self.session.execute(stmt).scalar())

    def exists_by_ksef_number(self, ksef_reference_number: str) -> bool:
        stmt = select(
            select(InvoiceORM)
            .where(InvoiceORM.ksef_reference_number == ksef_reference_number)
            .exists()
        )
        return bool(self.session.execute(stmt).scalar())

    def count_ksef_purchases_in_issue_range(
        self,
        date_from: date,
        date_to: date,
        buyer_nip: str | None = None,
    ) -> int:
        """Liczba faktur zakupowych z numerem KSeF w zakresie issue_date (audyt sync)."""
        return len(
            self.list_ksef_purchase_refs_in_issue_range(
                date_from,
                date_to,
                buyer_nip=buyer_nip,
            )
        )

    def list_ksef_purchase_refs_in_issue_range(
        self,
        date_from: date,
        date_to: date,
        buyer_nip: str | None = None,
    ) -> list[str]:
        """Numery KSeF faktur zakupowych w zakresie issue_date (opcjonalnie filtr NIP nabywcy)."""
        stmt = select(InvoiceORM.ksef_reference_number).where(
            InvoiceORM.direction == "purchase",
            InvoiceORM.ksef_reference_number.isnot(None),
            InvoiceORM.issue_date >= date_from,
            InvoiceORM.issue_date <= date_to,
        )
        if buyer_nip:
            normalized = buyer_nip.replace("-", "").replace(" ", "")
            buyer_nip_expr = func.replace(
                func.replace(InvoiceORM.buyer_snapshot_json["nip"].astext, "-", ""),
                " ",
                "",
            )
            stmt = stmt.where(buyer_nip_expr == normalized)

        rows = self.session.execute(stmt.order_by(InvoiceORM.issue_date.asc())).scalars().all()
        return [ref for ref in rows if isinstance(ref, str) and ref]

    def get_next_sequence_number(self, year: int, month: int) -> int:
        """Zlicza faktury w danym miesiącu i zwraca następny numer sekwencyjny."""
        from datetime import date as _date
        month_start = _date(year, month, 1)
        if month == 12:
            month_end = _date(year + 1, 1, 1)
        else:
            month_end = _date(year, month + 1, 1)

        stmt = select(func.count(InvoiceORM.id)).where(
            InvoiceORM.issue_date >= month_start,
            InvoiceORM.issue_date < month_end,
            InvoiceORM.number_local.isnot(None),
            InvoiceORM.direction == "sale",
        )
        count = self.session.execute(stmt).scalar_one()
        return count + 1

    def list_all(self) -> list:
        """Zwraca wszystkie faktury jako obiekty ORM (do matchingu płatności)."""
        stmt = select(InvoiceORM).order_by(InvoiceORM.issue_date.desc())
        return list(self.session.execute(stmt).scalars())
