#!/usr/bin/env python3
"""Naprawa totals_json faktur zakupowych z sum pozycji invoice_items.

Domyślnie dry-run. Działa tylko dla direction='purchase'.
Nie modyfikuje faktur sprzedaży.

Użycie:
    .venv/bin/python scripts/repair_purchase_totals_from_items.py
    .venv/bin/python scripts/repair_purchase_totals_from_items.py --apply
    .venv/bin/python scripts/repair_purchase_totals_from_items.py --report /tmp/repair.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.persistence.db import session_scope  # noqa: E402
from app.persistence.models.invoice import InvoiceORM  # noqa: E402
from app.persistence.models.invoice_item import InvoiceItemORM  # noqa: E402


def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _needs_repair(totals: dict | None, items_net: Decimal, items_vat: Decimal) -> bool:
    totals = totals or {}
    header_net = _dec(totals.get("total_net"))
    header_vat = _dec(totals.get("total_vat"))
    if header_net > 0 and header_vat > 0:
        return False
    if items_net <= 0 and items_vat <= 0:
        return False
    return header_net == 0 or header_vat == 0


def find_candidates(session) -> list[dict]:
    rows = session.execute(
        select(
            InvoiceORM.id,
            InvoiceORM.number_local,
            InvoiceORM.ksef_reference_number,
            InvoiceORM.issue_date,
            InvoiceORM.totals_json,
            InvoiceORM.seller_snapshot_json,
            func.coalesce(func.sum(InvoiceItemORM.net_amount), 0).label("sum_net"),
            func.coalesce(func.sum(InvoiceItemORM.vat_amount), 0).label("sum_vat"),
            func.coalesce(func.sum(InvoiceItemORM.gross_amount), 0).label("sum_gross"),
            func.count(InvoiceItemORM.id).label("item_count"),
        )
        .join(InvoiceItemORM, InvoiceItemORM.invoice_id == InvoiceORM.id)
        .where(InvoiceORM.direction == "purchase")
        .group_by(InvoiceORM.id)
    ).all()

    candidates: list[dict] = []
    for row in rows:
        totals = row.totals_json or {}
        items_net = _dec(row.sum_net)
        items_vat = _dec(row.sum_vat)
        items_gross = _dec(row.sum_gross)
        if not _needs_repair(totals, items_net, items_vat):
            continue
        header_gross = _dec(totals.get("total_gross"))
        new_gross = header_gross if header_gross > 0 else items_gross
        new_vat = items_vat
        if new_vat == 0 and new_gross > items_net > 0:
            new_vat = new_gross - items_net
        candidates.append(
            {
                "invoice_id": str(row.id),
                "number_local": row.number_local,
                "ksef_reference_number": row.ksef_reference_number,
                "issue_date": row.issue_date.isoformat() if row.issue_date else None,
                "seller_name": (row.seller_snapshot_json or {}).get("name"),
                "item_count": int(row.item_count),
                "old_totals": totals,
                "new_totals": {
                    "total_net": str(items_net),
                    "total_vat": str(new_vat),
                    "total_gross": str(new_gross),
                },
                "items_sum": {
                    "net": str(items_net),
                    "vat": str(items_vat),
                    "gross": str(items_gross),
                },
            }
        )
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair purchase totals_json from invoice_items")
    parser.add_argument("--apply", action="store_true", help="Zapisz zmiany (domyślnie dry-run)")
    parser.add_argument("--report", default="", help="Ścieżka raportu JSON")
    args = parser.parse_args()

    with session_scope() as session:
        candidates = find_candidates(session)
        print(f"Kandydaci do naprawy: {len(candidates)}")
        for entry in candidates[:20]:
            print(
                f"  {entry['number_local']} ref={entry['ksef_reference_number']} "
                f"old={entry['old_totals']} -> new={entry['new_totals']}"
            )
        if len(candidates) > 20:
            print(f"  ... i {len(candidates) - 20} więcej")

        if args.apply and candidates:
            for entry in candidates:
                inv = session.get(InvoiceORM, UUID(entry["invoice_id"]))
                if inv is None:
                    continue
                inv.totals_json = entry["new_totals"]
            print(f"Zaktualizowano: {len(candidates)} faktur purchase")
        elif not args.apply:
            print("Dry-run — użyj --apply aby zapisać (wymaga pg_dump przed apply na produkcji).")

    report_path = (
        Path(args.report)
        if args.report
        else ROOT / "docs" / "KSEF_PURCHASE_TOTALS_REPAIR_REPORT.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "dry_run": not args.apply,
                "count": len(candidates),
                "candidates": candidates,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Raport: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
