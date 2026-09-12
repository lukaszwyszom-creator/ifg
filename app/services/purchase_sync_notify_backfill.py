"""Jednorazowy backfill powiadomień o fakturach zakupowych pominiętych przez false SYNC_INCOMPLETE.

Użycie (produkcja, po wdrożeniu fixu):
  python -m app.services.purchase_sync_notify_backfill --dry-run
  python -m app.services.purchase_sync_notify_backfill --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.db import SessionLocal
from app.persistence.models.idempotency_key import IdempotencyKeyORM
from app.persistence.models.invoice import InvoiceORM
from app.persistence.models.purchase_sync_notification import PurchaseSyncNotificationORM
from app.persistence.repositories.idempotency_repository import IdempotencyRepository
from app.services.purchase_sync_email_notifier import (
    BACKFILL_CORRELATION_ID,
    BACKFILL_EMAIL_SUBJECT,
    BACKFILL_IDEMPOTENCY_KEY,
    BACKFILL_IDEMPOTENCY_SCOPE,
    PurchaseSyncEmailNotifier,
)

logger = logging.getLogger(__name__)

_EXPECTED_COUNT = 11
_WARSAW = ZoneInfo("Europe/Warsaw")
# Inclusive lower bound: first slot after last successful mail (2026-09-01 08:00 SENT).
_MISS_FROM = datetime(2026, 9, 1, 14, 0, 0, tzinfo=_WARSAW)
_MISS_TO = datetime(2026, 9, 12, 12, 0, 0, tzinfo=_WARSAW)


@dataclass(frozen=True)
class BackfillCandidate:
    invoice_id: str
    ksef_reference_number: str
    created_at_warsaw: str
    issue_date: str


@dataclass
class BackfillResult:
    status: str
    expected_count: int
    actual_count: int
    invoice_ids: list[str]
    ksef_refs: list[str]
    correlation_id: str
    idempotency_key: str
    email_attempted: bool
    email_result: str
    detail: str = ""


def _already_sent_invoice_ids(session: Session) -> set[str]:
    rows = session.execute(select(PurchaseSyncNotificationORM)).scalars().all()
    sent: set[str] = set()
    for row in rows:
        if row.status != "SENT" or row.notification_sent_at is None:
            continue
        for inv_id in row.new_invoice_ids or []:
            sent.add(str(inv_id))
    return sent


def collect_missed_purchase_invoices(session: Session) -> list[BackfillCandidate]:
    """Faktury zakupowe zapisane w oknie miss, nieujęte w żadnym SENT mailu."""
    sent_ids = _already_sent_invoice_ids(session)
    rows = list(
        session.execute(
            select(InvoiceORM)
            .where(
                InvoiceORM.direction == "purchase",
                InvoiceORM.created_at >= _MISS_FROM.astimezone(UTC),
                InvoiceORM.created_at < _MISS_TO.astimezone(UTC),
                InvoiceORM.ksef_reference_number.isnot(None),
            )
            .order_by(InvoiceORM.created_at.asc())
        ).scalars()
    )
    out: list[BackfillCandidate] = []
    for inv in rows:
        inv_id = str(inv.id)
        if inv_id in sent_ids:
            continue
        created = inv.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        out.append(
            BackfillCandidate(
                invoice_id=inv_id,
                ksef_reference_number=str(inv.ksef_reference_number),
                created_at_warsaw=created.astimezone(_WARSAW).isoformat(),
                issue_date=inv.issue_date.isoformat() if inv.issue_date else "",
            )
        )
    return out


def _idempotency_already_done(session: Session) -> IdempotencyKeyORM | None:
    repo = IdempotencyRepository(session)
    row = repo.get_by_scope_and_key(BACKFILL_IDEMPOTENCY_SCOPE, BACKFILL_IDEMPOTENCY_KEY)
    if row is not None and row.status in {"completed", "sent", "ALREADY_SENT"}:
        return row
    existing_notify = session.execute(
        select(PurchaseSyncNotificationORM).where(
            PurchaseSyncNotificationORM.correlation_id == BACKFILL_CORRELATION_ID
        )
    ).scalar_one_or_none()
    if existing_notify is not None and existing_notify.status == "SENT":
        return row or existing_notify  # type: ignore[return-value]
    return None


def run_backfill(*, apply: bool, expected_count: int = _EXPECTED_COUNT) -> BackfillResult:
    session = SessionLocal()
    try:
        if _idempotency_already_done(session) is not None:
            existing = session.execute(
                select(PurchaseSyncNotificationORM).where(
                    PurchaseSyncNotificationORM.correlation_id == BACKFILL_CORRELATION_ID
                )
            ).scalar_one_or_none()
            ids = [str(x) for x in (existing.new_invoice_ids if existing else [])]
            return BackfillResult(
                status="ALREADY_SENT",
                expected_count=expected_count,
                actual_count=len(ids) or expected_count,
                invoice_ids=ids,
                ksef_refs=[],
                correlation_id=str(BACKFILL_CORRELATION_ID),
                idempotency_key=BACKFILL_IDEMPOTENCY_KEY,
                email_attempted=False,
                email_result="ALREADY_SENT",
                detail="Idempotency key or SENT notification already present",
            )

        candidates = collect_missed_purchase_invoices(session)
        invoice_ids = [c.invoice_id for c in candidates]
        ksef_refs = [c.ksef_reference_number for c in candidates]

        if len(candidates) != expected_count:
            return BackfillResult(
                status="BACKFILL_COUNT_MISMATCH",
                expected_count=expected_count,
                actual_count=len(candidates),
                invoice_ids=invoice_ids,
                ksef_refs=ksef_refs,
                correlation_id=str(BACKFILL_CORRELATION_ID),
                idempotency_key=BACKFILL_IDEMPOTENCY_KEY,
                email_attempted=False,
                email_result="NOT_ATTEMPTED",
                detail=f"expected {expected_count}, got {len(candidates)}",
            )

        if not apply:
            return BackfillResult(
                status="DRY_RUN_OK",
                expected_count=expected_count,
                actual_count=len(candidates),
                invoice_ids=invoice_ids,
                ksef_refs=ksef_refs,
                correlation_id=str(BACKFILL_CORRELATION_ID),
                idempotency_key=BACKFILL_IDEMPOTENCY_KEY,
                email_attempted=False,
                email_result="DRY_RUN",
                detail=f"subject={BACKFILL_EMAIL_SUBJECT}",
            )

        # Persist idempotency marker before send to block concurrent re-entry.
        idemp_repo = IdempotencyRepository(session)
        existing_key = idemp_repo.get_by_scope_and_key(
            BACKFILL_IDEMPOTENCY_SCOPE, BACKFILL_IDEMPOTENCY_KEY
        )
        if existing_key is None:
            idemp_repo.add(
                BACKFILL_IDEMPOTENCY_SCOPE,
                BACKFILL_IDEMPOTENCY_KEY,
                status="pending",
                body_hash=str(expected_count),
            )
            session.commit()

        notifier = PurchaseSyncEmailNotifier(session)
        started = _MISS_FROM.astimezone(UTC)
        finished = datetime.now(UTC)
        uuids = [UUID(x) for x in invoice_ids]
        gross = notifier._compute_gross_sum(uuids)
        recipients = notifier._resolve_recipients()
        if not recipients:
            session.rollback()
            return BackfillResult(
                status="BLOCKED",
                expected_count=expected_count,
                actual_count=len(candidates),
                invoice_ids=invoice_ids,
                ksef_refs=ksef_refs,
                correlation_id=str(BACKFILL_CORRELATION_ID),
                idempotency_key=BACKFILL_IDEMPOTENCY_KEY,
                email_attempted=False,
                email_result="NO_RECIPIENTS",
            )

        row = PurchaseSyncNotificationORM(
            id=UUID("a11c0ffe-2026-0912-b001-000000000002"),
            correlation_id=BACKFILL_CORRELATION_ID,
            status="PENDING",
            sync_status="SUCCESS",
            started_at=started,
            finished_at=finished,
            new_invoice_ids=invoice_ids,
            invoice_count=len(invoice_ids),
            gross_sum=gross,
            skipped_duplicates=0,
            errors_count=0,
            recipient_email=",".join(recipients),
            max_attempts=1,
            attempt_count=0,
        )
        session.add(row)
        session.flush()
        notifier._send_row(row)
        session.refresh(row)

        if row.status != "SENT" or row.notification_sent_at is None:
            session.commit()
            return BackfillResult(
                status="EMAIL_FAILED",
                expected_count=expected_count,
                actual_count=len(candidates),
                invoice_ids=invoice_ids,
                ksef_refs=ksef_refs,
                correlation_id=str(BACKFILL_CORRELATION_ID),
                idempotency_key=BACKFILL_IDEMPOTENCY_KEY,
                email_attempted=True,
                email_result=row.status,
                detail=(row.last_error or "")[:200],
            )

        key_row = idemp_repo.get_by_scope_and_key(
            BACKFILL_IDEMPOTENCY_SCOPE, BACKFILL_IDEMPOTENCY_KEY
        )
        if key_row is not None:
            key_row.status = "completed"
            key_row.response_snapshot_json = {
                "notification_id": str(row.id),
                "invoice_count": len(invoice_ids),
                "sent_at": row.notification_sent_at.isoformat()
                if row.notification_sent_at
                else None,
            }
        session.commit()
        return BackfillResult(
            status="SENT",
            expected_count=expected_count,
            actual_count=len(candidates),
            invoice_ids=invoice_ids,
            ksef_refs=ksef_refs,
            correlation_id=str(BACKFILL_CORRELATION_ID),
            idempotency_key=BACKFILL_IDEMPOTENCY_KEY,
            email_attempted=True,
            email_result="SENT",
        )
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Only collect and validate count")
    parser.add_argument("--apply", action="store_true", help="Send the one-shot backfill email")
    parser.add_argument("--expected-count", type=int, default=_EXPECTED_COUNT)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        print("Use either --dry-run or --apply, not both", file=sys.stderr)
        return 2
    if not args.apply and not args.dry_run:
        args.dry_run = True

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_backfill(apply=bool(args.apply), expected_count=args.expected_count)
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    if result.status in {"SENT", "DRY_RUN_OK", "ALREADY_SENT"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
