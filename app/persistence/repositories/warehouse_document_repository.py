from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models.warehouse_document import (
    WarehouseBalanceORM,
    WarehouseDocumentItemORM,
    WarehouseDocumentORM,
)


class WarehouseDocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, doc_id: UUID) -> WarehouseDocumentORM | None:
        return self.session.get(WarehouseDocumentORM, doc_id)

    def get_by_id_with_items(self, doc_id: UUID) -> WarehouseDocumentORM | None:
        stmt = (
            select(WarehouseDocumentORM)
            .options(selectinload(WarehouseDocumentORM.doc_items))
            .where(WarehouseDocumentORM.id == doc_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        doc_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WarehouseDocumentORM]:
        stmt = (
            select(WarehouseDocumentORM)
            .order_by(WarehouseDocumentORM.created_at.desc())
        )
        if doc_type:
            stmt = stmt.where(WarehouseDocumentORM.doc_type == doc_type)
        if status:
            stmt = stmt.where(WarehouseDocumentORM.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def count(self, doc_type: str | None = None, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(WarehouseDocumentORM)
        if doc_type:
            stmt = stmt.where(WarehouseDocumentORM.doc_type == doc_type)
        if status:
            stmt = stmt.where(WarehouseDocumentORM.status == status)
        return self.session.execute(stmt).scalar_one()

    def add(self, doc: WarehouseDocumentORM) -> WarehouseDocumentORM:
        self.session.add(doc)
        self.session.flush()
        return doc

    def save(self, doc: WarehouseDocumentORM) -> WarehouseDocumentORM:
        self.session.add(doc)
        self.session.flush()
        return doc

    # ── numeracja ─────────────────────────────────────────────────────────────

    def count_posted_by_type_and_year(self, doc_type: str, year: int) -> int:
        """Zlicza zaksięgowane dokumenty danego typu w roku — do generacji numeru."""
        stmt = (
            select(func.count())
            .select_from(WarehouseDocumentORM)
            .where(
                WarehouseDocumentORM.doc_type == doc_type,
                WarehouseDocumentORM.number.is_not(None),
                WarehouseDocumentORM.number.like(f"{doc_type}/{year}/%"),
            )
        )
        return self.session.execute(stmt).scalar_one()

    # ── balance ───────────────────────────────────────────────────────────────

    def get_balance(self, item_id: UUID) -> WarehouseBalanceORM | None:
        return self.session.get(WarehouseBalanceORM, item_id)

    def upsert_balance(self, item_id: UUID, delta: object) -> WarehouseBalanceORM:
        """Dodaje delta do quantity_available. Tworzy rekord jeśli nie istnieje."""
        from decimal import Decimal
        delta_dec = Decimal(str(delta))
        balance = self.get_balance(item_id)
        if balance is None:
            balance = WarehouseBalanceORM(
                item_id=item_id,
                quantity_available=delta_dec,
            )
        else:
            balance.quantity_available += delta_dec
        self.session.add(balance)
        self.session.flush()
        return balance
