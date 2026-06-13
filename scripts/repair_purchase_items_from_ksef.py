#!/usr/bin/env python3
"""Backfill invoice_items dla faktur KSeF purchase z zerowymi kwotami pozycji.

Strategia:
1. Pobierz XML z KSeF (GET /invoices/ksef/{ref}) i sparsuj nowym parserem FA(3).
2. Fallback: jedna pozycja z nazwą + poprawne totals_json → uzupełnij kwoty z nagłówka.

Domyślnie dry-run. Tylko direction='purchase'. Nie zmienia totals_json ani faktur sale.

Użycie:
    .venv/bin/python scripts/repair_purchase_items_from_ksef.py
    .venv/bin/python scripts/repair_purchase_items_from_ksef.py --apply
    .venv/bin/python scripts/repair_purchase_items_from_ksef.py --number FAS/BYD/999/2026
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.integrations.ksef.auth import KSeFAuthError, KSeFAuthProvider  # noqa: E402
from app.integrations.ksef.client import KSeFClient, KSeFClientError  # noqa: E402
from app.integrations.ksef.xml_parser import (  # noqa: E402
    parse_fa3_xml,
    parsed_invoice_has_nonzero_items,
    purchase_items_validation_error,
)
from app.persistence.db import session_scope  # noqa: E402
from app.persistence.models.invoice import InvoiceORM  # noqa: E402
from app.persistence.models.invoice_item import InvoiceItemORM  # noqa: E402
from app.persistence.models.ksef_session import KSeFSessionORM  # noqa: E402

_ACCESS_TOKEN_KEY = "access_token"
_TWO = Decimal("0.01")


def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(_TWO, rounding=ROUND_HALF_UP)


def _resolve_access_token(*, auth: str, nip: str) -> str:
    if auth == "session":
        with session_scope() as db:
            orm = db.execute(
                select(KSeFSessionORM)
                .where(KSeFSessionORM.nip == nip, KSeFSessionORM.status == "active")
                .order_by(KSeFSessionORM.updated_at.desc())
            ).scalars().first()
            if orm is None:
                raise SystemExit(f"Brak aktywnej sesji KSeF dla NIP={nip}")
            token = (orm.token_metadata_json or {}).get(_ACCESS_TOKEN_KEY)
            if not token:
                raise SystemExit(f"Brak {_ACCESS_TOKEN_KEY} w token_metadata_json sesji {orm.id}")
            return token

    ksef_token = settings.ksef_auth_token
    if not ksef_token:
        raise SystemExit("Brak KSEF_AUTH_TOKEN — użyj --auth session lub ustaw token w .env")
    provider = KSeFAuthProvider(
        environment=settings.ksef_environment,
        timeout_seconds=settings.ksef_timeout_seconds,
        auth_redeem_timeout_seconds=settings.ksef_auth_redeem_timeout_seconds,
    )
    try:
        session = provider.get_tokens(nip=nip, ksef_auth_token=ksef_token)
    except KSeFAuthError as exc:
        raise SystemExit(f"Błąd uwierzytelnienia KSeF: {exc}") from exc
    return session.access_token


def _item_is_zero(row: InvoiceItemORM) -> bool:
    return _dec(row.net_amount) == 0 and _dec(row.vat_amount) == 0 and _dec(row.gross_amount) == 0


def find_candidates(session, *, number_local: str | None = None) -> list[dict]:
    stmt = (
        select(
            InvoiceORM.id,
            InvoiceORM.number_local,
            InvoiceORM.ksef_reference_number,
            InvoiceORM.issue_date,
            InvoiceORM.totals_json,
            InvoiceORM.seller_snapshot_json,
            func.count(InvoiceItemORM.id).label("item_count"),
            func.coalesce(func.sum(InvoiceItemORM.net_amount), 0).label("sum_net"),
            func.coalesce(func.sum(InvoiceItemORM.gross_amount), 0).label("sum_gross"),
        )
        .join(InvoiceItemORM, InvoiceItemORM.invoice_id == InvoiceORM.id)
        .where(InvoiceORM.direction == "purchase")
        .group_by(InvoiceORM.id)
    )
    if number_local:
        stmt = stmt.where(InvoiceORM.number_local == number_local)

    rows = session.execute(stmt).all()
    candidates: list[dict] = []
    for row in rows:
        totals = row.totals_json or {}
        if _dec(totals.get("total_gross")) <= 0:
            continue
        if _dec(row.sum_net) > 0 or _dec(row.sum_gross) > 0:
            continue
        if not row.ksef_reference_number:
            continue
        candidates.append(
            {
                "invoice_id": str(row.id),
                "number_local": row.number_local,
                "ksef_reference_number": row.ksef_reference_number,
                "issue_date": row.issue_date.isoformat() if row.issue_date else None,
                "seller_name": (row.seller_snapshot_json or {}).get("name"),
                "totals_json": row.totals_json or {},
                "item_count": int(row.item_count),
            }
        )
    return candidates


def _parsed_items_to_dicts(parsed: dict) -> list[dict]:
    items: list[dict] = []
    for item in parsed.get("items") or []:
        items.append(
            {
                "name": item.get("name") or "",
                "quantity": _dec(item.get("quantity", 1)),
                "unit": item.get("unit") or "szt.",
                "unit_price_net": _dec(item.get("unit_price_net", 0)),
                "vat_rate": _dec(item.get("vat_rate", 0)),
                "net_amount": _dec(item.get("net_total", 0)),
                "vat_amount": _dec(item.get("vat_total", 0)),
                "gross_amount": _dec(item.get("gross_total", 0)),
                "sort_order": int(item.get("sort_order", 0)),
            }
        )
    return items


def _fallback_items_from_totals(
    existing: list[InvoiceItemORM],
    totals: dict,
) -> list[dict] | None:
    if len(existing) != 1:
        return None
    totals = totals or {}
    net = _dec(totals.get("total_net"))
    vat = _dec(totals.get("total_vat"))
    gross = _dec(totals.get("total_gross"))
    if gross <= 0 or net <= 0:
        return None

    row = existing[0]
    qty = _dec(row.quantity) if _dec(row.quantity) > 0 else Decimal("1")
    vat_rate = _dec(row.vat_rate)
    if vat_rate == 0 and net > 0 and vat > 0:
        vat_rate = (vat / net * Decimal("100")).quantize(_TWO, rounding=ROUND_HALF_UP)

    unit_price_net = (net / qty).quantize(_TWO, rounding=ROUND_HALF_UP)
    return [
        {
            "name": row.name,
            "quantity": qty,
            "unit": row.unit or "szt.",
            "unit_price_net": unit_price_net,
            "vat_rate": vat_rate,
            "net_amount": net,
            "vat_amount": vat,
            "gross_amount": gross if gross > 0 else net + vat,
            "sort_order": row.sort_order,
        }
    ]


def _fetch_parsed_items(
    client: KSeFClient,
    access_token: str,
    ksef_ref: str,
) -> tuple[list[dict] | None, str]:
    try:
        xml_bytes = client._get_purchase_invoice_xml(access_token, ksef_ref)  # noqa: SLF001
    except KSeFClientError as exc:
        return None, f"ksef_fetch: {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, f"ksef_fetch: {exc}"

    try:
        parsed = parse_fa3_xml(xml_bytes)
    except Exception as exc:  # noqa: BLE001
        return None, f"parse: {exc}"

    err = purchase_items_validation_error(parsed)
    if err:
        return None, err
    if not parsed_invoice_has_nonzero_items(parsed):
        return None, "parsed items still zero"
    return _parsed_items_to_dicts(parsed), "ksef_xml"


def _apply_items(session, invoice_id: UUID, new_items: list[dict]) -> None:
    existing = session.execute(
        select(InvoiceItemORM)
        .where(InvoiceItemORM.invoice_id == invoice_id)
        .order_by(InvoiceItemORM.sort_order, InvoiceItemORM.id)
    ).scalars().all()

    if len(existing) == len(new_items):
        for orm_row, data in zip(existing, new_items, strict=True):
            orm_row.name = data["name"]
            orm_row.quantity = data["quantity"]
            orm_row.unit = data["unit"]
            orm_row.unit_price_net = data["unit_price_net"]
            orm_row.vat_rate = data["vat_rate"]
            orm_row.net_amount = data["net_amount"]
            orm_row.vat_amount = data["vat_amount"]
            orm_row.gross_amount = data["gross_amount"]
            orm_row.sort_order = data["sort_order"]
        return

    session.execute(delete(InvoiceItemORM).where(InvoiceItemORM.invoice_id == invoice_id))
    for data in new_items:
        session.add(
            InvoiceItemORM(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                name=data["name"],
                quantity=data["quantity"],
                unit=data["unit"],
                unit_price_net=data["unit_price_net"],
                vat_rate=data["vat_rate"],
                net_amount=data["net_amount"],
                vat_amount=data["vat_amount"],
                gross_amount=data["gross_amount"],
                sort_order=data["sort_order"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair purchase invoice_items from KSeF XML or totals")
    parser.add_argument("--apply", action="store_true", help="Zapisz zmiany (domyślnie dry-run)")
    parser.add_argument("--auth", choices=("session", "fresh"), default="session")
    parser.add_argument("--nip", default="", help="NIP (domyślnie settings.seller_nip)")
    parser.add_argument("--number", default="", help="Tylko wskazany number_local")
    parser.add_argument("--no-ksef", action="store_true", help="Pomiń pobieranie z KSeF, tylko fallback totals")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pauza między requestami KSeF (s)")
    parser.add_argument("--report", default="", help="Ścieżka raportu JSON")
    args = parser.parse_args()

    nip = (args.nip or settings.seller_nip or "").strip()
    if not nip and not args.no_ksef:
        raise SystemExit("Podaj --nip lub ustaw SELLER_NIP")

    access_token = ""
    client: KSeFClient | None = None
    if not args.no_ksef:
        access_token = _resolve_access_token(auth=args.auth, nip=nip)
        client = KSeFClient(
            environment=settings.ksef_environment,
            timeout_seconds=settings.ksef_timeout_seconds,
        )

    results: list[dict] = []
    with session_scope() as session:
        candidates = find_candidates(session, number_local=args.number or None)
        print(f"Kandydaci: {len(candidates)}")

        for entry in candidates:
            invoice_id = UUID(entry["invoice_id"])
            existing = session.execute(
                select(InvoiceItemORM)
                .where(InvoiceItemORM.invoice_id == invoice_id)
                .order_by(InvoiceItemORM.sort_order, InvoiceItemORM.id)
            ).scalars().all()
            if not existing or not all(_item_is_zero(row) for row in existing):
                continue

            new_items: list[dict] | None = None
            source = ""
            error = ""

            if client and access_token:
                new_items, source_or_err = _fetch_parsed_items(
                    client, access_token, entry["ksef_reference_number"]
                )
                if new_items:
                    source = source_or_err
                else:
                    error = source_or_err
                time.sleep(max(0.0, args.sleep))

            if new_items is None:
                new_items = _fallback_items_from_totals(existing, entry["totals_json"])
                if new_items:
                    source = "totals_fallback"
                elif not error:
                    error = "brak danych z KSeF i fallback totals niemożliwy"

            record = {
                **entry,
                "source": source,
                "error": error,
                "new_items": new_items,
                "applied": False,
            }

            if new_items:
                preview = new_items[0]
                print(
                    f"  {entry['number_local']} ref={entry['ksef_reference_number']} "
                    f"src={source} net={preview['net_amount']} vat={preview['vat_amount']} "
                    f"gross={preview['gross_amount']}"
                )
                if args.apply:
                    _apply_items(session, invoice_id, new_items)
                    record["applied"] = True
            else:
                print(f"  SKIP {entry['number_local']}: {error}")

            results.append(record)

        if args.apply:
            applied = sum(1 for r in results if r.get("applied"))
            print(f"Zaktualizowano pozycje: {applied} faktur")
        else:
            print("Dry-run — użyj --apply (wymaga pg_dump przed apply na produkcji).")

    report_path = (
        Path(args.report)
        if args.report
        else ROOT / "docs" / "KSEF_PURCHASE_ITEMS_REPAIR_REPORT.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "dry_run": not args.apply,
                "count": len(results),
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Raport: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
