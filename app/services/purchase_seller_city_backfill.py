"""Backfill seller_snapshot.city dla faktur zakupowych (GWO-IFG-0029).

Uruchomienie w kontenerze API:
  python -m app.services.purchase_seller_city_backfill
  python -m app.services.purchase_seller_city_backfill --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.integrations.ksef.fa3_address import extract_city_only_from_stored_address_fields
from app.persistence.db import session_scope
from app.persistence.models.invoice import InvoiceORM


def _city_empty(snapshot: dict | None) -> bool:
    if not isinstance(snapshot, dict):
        return True
    return not str(snapshot.get("city") or "").strip()


def classify_candidate(orm: InvoiceORM) -> dict:
    snap = dict(orm.seller_snapshot_json or {})
    proposed = extract_city_only_from_stored_address_fields(
        street=str(snap.get("street") or ""),
        apartment_no=str(snap.get("apartment_no") or ""),
        postal_code=str(snap.get("postal_code") or ""),
        city=str(snap.get("city") or ""),
    )
    if not _city_empty(snap):
        category = "SKIP_ALREADY_SET"
    elif proposed:
        category = "A_REPAIRABLE"
    elif orm.ksef_reference_number:
        category = "B_NEEDS_KSEF_REFETCH"
    else:
        category = "C_UNRESOLVED_NO_SOURCE"

    return {
        "id": str(orm.id),
        "number_local": orm.number_local,
        "ksef_reference_number": orm.ksef_reference_number,
        "category": category,
        "proposed_city": proposed,
        "name": str(snap.get("name") or "")[:80],
        "street": str(snap.get("street") or "")[:120],
        "apartment_no": str(snap.get("apartment_no") or "")[:80],
    }


def find_candidates(*, limit: int | None = None) -> list[dict]:
    with session_scope() as db:
        stmt = (
            select(InvoiceORM)
            .where(InvoiceORM.direction == "purchase")
            .order_by(InvoiceORM.created_at.asc())
        )
        rows = list(db.execute(stmt).scalars().all())
        out: list[dict] = []
        for orm in rows:
            if not _city_empty(orm.seller_snapshot_json):
                continue
            out.append(classify_candidate(orm))
            if limit is not None and len(out) >= limit:
                break
        return out


def apply_repairs(candidates: list[dict], *, chunk_size: int = 100) -> dict:
    repairable = [c for c in candidates if c["category"] == "A_REPAIRABLE" and c["proposed_city"]]
    updated = 0
    unchanged = 0
    errors: list[str] = []

    for i in range(0, len(repairable), chunk_size):
        chunk = repairable[i : i + chunk_size]
        with session_scope() as db:
            for item in chunk:
                orm = db.get(InvoiceORM, UUID(item["id"]))
                if orm is None:
                    errors.append(f"missing:{item['id']}")
                    continue
                snap = dict(orm.seller_snapshot_json or {})
                if str(snap.get("city") or "").strip():
                    unchanged += 1
                    continue
                proposed = item["proposed_city"]
                recomputed = extract_city_only_from_stored_address_fields(
                    street=str(snap.get("street") or ""),
                    apartment_no=str(snap.get("apartment_no") or ""),
                    postal_code=str(snap.get("postal_code") or ""),
                    city="",
                )
                if recomputed != proposed or not recomputed:
                    errors.append(f"mismatch:{item['id']}")
                    continue
                snap["city"] = recomputed
                orm.seller_snapshot_json = snap
                flag_modified(orm, "seller_snapshot_json")
                updated += 1

    return {
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
        "repairable_input": len(repairable),
    }


def run_backfill(*, apply: bool = False, limit: int | None = None, report_path: Path | None = None) -> dict:
    candidates = find_candidates(limit=limit)
    by_cat: dict[str, int] = {}
    for c in candidates:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "apply" if apply else "dry-run",
        "empty_city_candidates": len(candidates),
        "by_category": by_cat,
        "proposed_repairs": [
            {
                "id": c["id"],
                "number_local": c["number_local"],
                "proposed_city": c["proposed_city"],
                "name": c["name"],
            }
            for c in candidates
            if c["category"] == "A_REPAIRABLE"
        ],
        "unresolved": [
            {
                "id": c["id"],
                "number_local": c["number_local"],
                "category": c["category"],
                "ksef_reference_number": c["ksef_reference_number"],
                "name": c["name"],
                "street": c["street"],
                "apartment_no": c["apartment_no"],
            }
            for c in candidates
            if c["category"] in {"B_NEEDS_KSEF_REFETCH", "C_UNRESOLVED_NO_SOURCE"}
        ],
        "apply_result": None,
        "second_pass_a_repairable": None,
    }

    print(f"MODE={'apply' if apply else 'dry-run'}")
    print(f"EMPTY_CITY_CANDIDATES={len(candidates)}")
    print(f"BY_CATEGORY={json.dumps(by_cat, ensure_ascii=False)}")
    print(f"A_REPAIRABLE={by_cat.get('A_REPAIRABLE', 0)}")
    print(f"B_NEEDS_KSEF_REFETCH={by_cat.get('B_NEEDS_KSEF_REFETCH', 0)}")
    print(f"C_UNRESOLVED_NO_SOURCE={by_cat.get('C_UNRESOLVED_NO_SOURCE', 0)}")

    if apply:
        result = apply_repairs(candidates)
        report["apply_result"] = result
        print(f"UPDATED={result['updated']}")
        print(f"UNCHANGED={result['unchanged']}")
        print(f"ERRORS={len(result['errors'])}")
        remaining = find_candidates(limit=limit)
        a2 = sum(1 for c in remaining if c["category"] == "A_REPAIRABLE")
        print(f"SECOND_PASS_A_REPAIRABLE={a2}")
        report["second_pass_a_repairable"] = a2

    if report_path is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        report_path = Path("/tmp") / f"GWO-IFG-0029_seller_city_backfill_{stamp}.json"
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REPORT={report_path}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Zapisz city (domyślnie dry-run)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)
    run_backfill(apply=args.apply, limit=args.limit, report_path=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
