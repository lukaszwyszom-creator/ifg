#!/usr/bin/env python3
"""Backfill warstw FIFO dla istniejących PZ draft (E2).

Uruchomienie:
  python -m scripts.backfill_pz_draft_layers --dry-run
  python -m scripts.backfill_pz_draft_layers --execute [--batch-id UUID]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.db import session_scope
from app.persistence.models.inventory_layer import InventoryLayerORM
from app.persistence.models.warehouse_document import (
    WarehouseDocumentItemORM,
    WarehouseDocumentORM,
    WarehouseBalanceORM,
)
from app.persistence.models.warehouse_item import WarehouseItemORM


@dataclass(frozen=True)
class BackfillCandidate:
    doc_id: UUID
    doc_item_id: UUID
    item_id: UUID
    quantity: Decimal
    received_date: date


def fetch_candidates(session: Session) -> list[BackfillCandidate]:
    stmt = (
        select(
            WarehouseDocumentORM.id,
            WarehouseDocumentItemORM.id,
            WarehouseDocumentItemORM.item_id,
            WarehouseDocumentItemORM.quantity,
            WarehouseDocumentORM.created_at,
        )
        .join(
            WarehouseDocumentItemORM,
            WarehouseDocumentItemORM.document_id == WarehouseDocumentORM.id,
        )
        .outerjoin(
            InventoryLayerORM,
            InventoryLayerORM.source_document_item_id == WarehouseDocumentItemORM.id,
        )
        .where(
            WarehouseDocumentORM.doc_type == "PZ",
            WarehouseDocumentORM.status == "draft",
            InventoryLayerORM.id.is_(None),
        )
        .order_by(WarehouseDocumentORM.created_at)
    )
    rows = session.execute(stmt).all()
    candidates: list[BackfillCandidate] = []
    for doc_id, doc_item_id, item_id, quantity, created_at in rows:
        if session.get(WarehouseItemORM, item_id) is None:
            raise RuntimeError(f"Brak towaru {item_id} dla pozycji PZ {doc_item_id}")
        qty = Decimal(str(quantity))
        if qty <= 0:
            continue
        recv_date = created_at.date() if created_at is not None else date.today()
        candidates.append(
            BackfillCandidate(
                doc_id=doc_id,
                doc_item_id=doc_item_id,
                item_id=item_id,
                quantity=qty,
                received_date=recv_date,
            )
        )
    return candidates


def backfill_pz_draft_layers(
    session: Session,
    *,
    dry_run: bool,
    batch_id: UUID,
) -> dict[str, int | str]:
    candidates = fetch_candidates(session)
    balance_delta: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    log_rows: list[dict] = []

    for cand in candidates:
        layer_id = uuid4()
        log_rows.append(
            {
                "action": "insert_layer",
                "batch_id": str(batch_id),
                "layer_id": str(layer_id),
                "doc_id": str(cand.doc_id),
                "doc_item_id": str(cand.doc_item_id),
                "item_id": str(cand.item_id),
                "quantity": str(cand.quantity),
            }
        )
        balance_delta[cand.item_id] += cand.quantity
        if dry_run:
            continue
        session.add(
            InventoryLayerORM(
                id=layer_id,
                item_id=cand.item_id,
                source_document_item_id=cand.doc_item_id,
                source_document_type="PZ",
                received_quantity=cand.quantity,
                remaining_quantity=cand.quantity,
                purchase_unit_price=None,
                received_date=cand.received_date,
                is_correction=False,
            )
        )

    if not dry_run:
        for item_id, delta in balance_delta.items():
            balance = session.get(WarehouseBalanceORM, item_id)
            if balance is None:
                session.add(
                    WarehouseBalanceORM(item_id=item_id, quantity_available=delta)
                )
            else:
                balance.quantity_available = Decimal(str(balance.quantity_available)) + delta

    return {
        "batch_id": str(batch_id),
        "candidates": len(candidates),
        "layers_inserted": 0 if dry_run else len(candidates),
        "items_balance_updated": 0 if dry_run else len(balance_delta),
        "dry_run": dry_run,
        "log": log_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill warstw FIFO dla PZ draft")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--batch-id", type=str, default=None)
    args = parser.parse_args(argv)

    batch_id = UUID(args.batch_id) if args.batch_id else uuid4()
    dry_run = args.dry_run

    with session_scope() as session:
        result = backfill_pz_draft_layers(session, dry_run=dry_run, batch_id=batch_id)
        if dry_run:
            session.rollback()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
