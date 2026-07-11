"""E-mail podsumowujący sesję synchronizacji zakupów KSeF."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import KSeFOperationType, KSeFSeverity
from app.integrations.email.smtp_client import SmtpConfig, SmtpSendError, send_email
from app.persistence.models.invoice import InvoiceORM
from app.persistence.models.purchase_sync_notification import PurchaseSyncNotificationORM
from app.persistence.repositories.purchase_sync_notification_repository import (
    PurchaseSyncNotificationRepository,
)
from app.services.ksef_purchase_sync_audit import PurchaseSyncAudit
from app.services.ksef_transmission_journal_service import KSeFTransmissionJournalService
from app.services.purchase_sync_notify_config import (
    infer_session_slot_label,
    parse_notify_recipients,
    retry_delay_seconds,
)

logger = logging.getLogger(__name__)

_EMAIL_SUBJECT = "IFG — nowe faktury zakupowe z KSeF"


@dataclass(frozen=True)
class InvoiceEmailLine:
    counterparty: str
    number: str
    issue_date: str
    gross_total: str
    gross_decimal: Decimal


class PurchaseSyncEmailNotifier:
    """Kolejka i wysyłka e-maili po sesji synchronizacji zakupów."""

    def __init__(
        self,
        session: Session,
        *,
        journal_service: KSeFTransmissionJournalService | None = None,
        notification_repository: PurchaseSyncNotificationRepository | None = None,
    ) -> None:
        self.session = session
        self._journal = journal_service
        self._repo = notification_repository or PurchaseSyncNotificationRepository(session)

    def maybe_enqueue_after_sync(
        self,
        *,
        correlation_id: UUID,
        operation_type: KSeFOperationType,
        audit: PurchaseSyncAudit,
        started_at: datetime,
        finished_at: datetime,
    ) -> PurchaseSyncNotificationORM | None:
        """Tworzy wpis PENDING — bez bezpośredniej wysyłki."""
        if not self._is_enabled():
            return None
        if operation_type != KSeFOperationType.PURCHASE_SYNC_AUTO:
            return None
        if audit.is_sync_incomplete():
            return None
        if audit.saved <= 0 or not audit.saved_invoice_ids:
            return None

        existing = self._repo.get_by_correlation_id(correlation_id)
        if existing is not None:
            return None

        recipients = self._resolve_recipients()
        if not recipients:
            logger.warning(
                "PURCHASE_SYNC_NOTIFY_ENABLED bez poprawnych odbiorców — pomijam kolejkę."
            )
            return None

        gross_sum = self._compute_gross_sum(audit.saved_invoice_ids)
        row = PurchaseSyncNotificationORM(
            id=uuid4(),
            correlation_id=correlation_id,
            status="PENDING",
            sync_status="SUCCESS",
            started_at=started_at,
            finished_at=finished_at,
            new_invoice_ids=[str(inv_id) for inv_id in audit.saved_invoice_ids],
            invoice_count=len(audit.saved_invoice_ids),
            gross_sum=gross_sum,
            skipped_duplicates=audit.skipped_existing,
            errors_count=audit.skipped_invalid + audit.skipped_error,
            recipient_email=",".join(recipients),
            max_attempts=settings.purchase_sync_notify_max_attempts,
            attempt_count=0,
        )
        self._repo.add(row)
        self._log_journal(
            correlation_id,
            event="enqueued",
            recipient_count=len(recipients),
        )
        logger.info(
            "PURCHASE_SYNC_NOTIFY_ENQUEUED correlation_id=%s new_invoices=%d recipients=%d",
            correlation_id,
            len(audit.saved_invoice_ids),
            len(recipients),
        )
        return row

    def process_pending(self, *, limit: int = 5) -> int:
        """Przetwarza kolejkę z atomowym przejęciem rekordów."""
        if not self._is_enabled():
            return 0

        rows = self._repo.claim_processable(limit=limit)
        processed = 0
        for row in rows:
            if row.notification_sent_at is not None:
                continue
            if row.status == "FAILED_PERMANENT":
                continue
            self._send_row(row)
            processed += 1
        return processed

    def _send_row(self, row: PurchaseSyncNotificationORM) -> None:
        smtp_config = self._smtp_config()
        attempt_no = self._repo.begin_attempt(row)
        max_attempts = int(row.max_attempts or settings.purchase_sync_notify_max_attempts)

        if smtp_config is None:
            error = "Brak konfiguracji SMTP (SMTP_HOST / SMTP_FROM)."
            outcome = self._repo.mark_retry_or_permanent(row, error)
            self._log_failure(row, attempt_no=attempt_no, max_attempts=max_attempts, error=error, outcome=outcome)
            return

        recipients = parse_notify_recipients(
            recipients_csv=row.recipient_email,
            legacy_email=None,
        )
        if not recipients:
            error = "Brak poprawnych odbiorców w rekordzie kolejki."
            outcome = self._repo.mark_retry_or_permanent(row, error)
            self._log_failure(row, attempt_no=attempt_no, max_attempts=max_attempts, error=error, outcome=outcome)
            return

        invoice_lines = self._load_invoice_lines(row.new_invoice_ids)
        body = self._render_body(row, invoice_lines)

        try:
            send_email(
                config=smtp_config,
                to_addrs=recipients,
                subject=_EMAIL_SUBJECT,
                body_text=body,
            )
        except SmtpSendError as exc:
            error = str(exc)
            outcome = self._repo.mark_retry_or_permanent(row, error)
            self._log_failure(
                row,
                attempt_no=attempt_no,
                max_attempts=max_attempts,
                error=error,
                outcome=outcome,
            )
            logger.warning(
                "PURCHASE_SYNC_NOTIFY_FAILED correlation_id=%s attempt=%d/%d error=%s",
                row.correlation_id,
                attempt_no,
                max_attempts,
                exc,
            )
            return

        self._repo.mark_sent(row)
        self._log_journal(
            row.correlation_id,
            event="sent",
            attempt_no=attempt_no,
            max_attempts=max_attempts,
            recipient_count=len(recipients),
        )
        logger.info(
            "PURCHASE_SYNC_NOTIFY_SENT correlation_id=%s attempt=%d recipients=%d",
            row.correlation_id,
            attempt_no,
            len(recipients),
        )

    def _compute_gross_sum(self, invoice_ids: list[UUID]) -> Decimal:
        if not invoice_ids:
            return Decimal("0")
        invoices = list(
            self.session.execute(select(InvoiceORM).where(InvoiceORM.id.in_(invoice_ids))).scalars()
        )
        total = Decimal("0")
        for inv in invoices:
            if (inv.direction or "").lower() != "purchase":
                continue
            totals = inv.totals_json if isinstance(inv.totals_json, dict) else {}
            try:
                total += Decimal(str(totals.get("total_gross", 0)))
            except Exception:
                continue
        return total.quantize(Decimal("0.01"))

    def _load_invoice_lines(self, raw_ids: list) -> list[InvoiceEmailLine]:
        if not raw_ids:
            return []

        ids: list[UUID] = []
        for raw in raw_ids:
            try:
                ids.append(UUID(str(raw)))
            except ValueError:
                continue
        if not ids:
            return []

        invoices = list(
            self.session.execute(select(InvoiceORM).where(InvoiceORM.id.in_(ids))).scalars()
        )
        by_id = {inv.id: inv for inv in invoices}
        lines: list[InvoiceEmailLine] = []
        for inv_id in ids:
            inv = by_id.get(inv_id)
            if inv is None:
                continue
            if (inv.direction or "").lower() != "purchase":
                continue
            seller = inv.seller_snapshot_json if isinstance(inv.seller_snapshot_json, dict) else {}
            totals = inv.totals_json if isinstance(inv.totals_json, dict) else {}
            gross = Decimal(str(totals.get("total_gross", 0)))
            lines.append(
                InvoiceEmailLine(
                    counterparty=str(seller.get("name") or "—"),
                    number=str(inv.number_local or "—"),
                    issue_date=inv.issue_date.isoformat() if inv.issue_date else "—",
                    gross_total=self._format_money(gross, inv.currency or "PLN"),
                    gross_decimal=gross,
                )
            )
        return lines

    @staticmethod
    def _format_money(value: object, currency: str) -> str:
        try:
            amount = Decimal(str(value))
        except Exception:
            return f"{value} {currency}"
        formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} {currency}"

    def _render_body(
        self,
        row: PurchaseSyncNotificationORM,
        invoice_lines: list[InvoiceEmailLine],
    ) -> str:
        started = row.started_at.astimezone().strftime("%d.%m.%Y %H:%M") if row.started_at else "—"
        finished = row.finished_at.astimezone().strftime("%d.%m.%Y %H:%M") if row.finished_at else "—"
        slot = infer_session_slot_label(row.finished_at)
        slot_line = f"Sesja: {slot}\n" if slot else ""

        lines_block = [
            f"- {line.counterparty} | {line.number} | {line.issue_date} | {line.gross_total}"
            for line in invoice_lines
        ]
        total_line = self._format_money(row.gross_sum, "PLN")
        invoice_list = "\n".join(lines_block) if lines_block else "(brak pozycji)"

        return (
            "Synchronizacja zakupów z KSeF została zakończona pomyślnie.\n\n"
            "Typ sesji: automatyczna\n"
            f"{slot_line}"
            f"Rozpoczęcie: {started}\n"
            f"Zakończenie: {finished}\n"
            f"Status: {row.sync_status}\n"
            f"Liczba nowych faktur: {row.invoice_count}\n"
            f"Pominięte duplikaty: {row.skipped_duplicates}\n"
            f"Błędy: {row.errors_count}\n"
            f"Suma brutto: {total_line}\n\n"
            f"Lista:\n{invoice_list}\n\n"
            "Szczegóły znajdują się w Monitorze KSeF.\n"
        )

    def _log_failure(
        self,
        row: PurchaseSyncNotificationORM,
        *,
        attempt_no: int,
        max_attempts: int,
        error: str,
        outcome: str,
    ) -> None:
        if outcome == "FAILED_PERMANENT":
            self._log_journal(
                row.correlation_id,
                event="permanent_failure",
                attempt_no=attempt_no,
                max_attempts=max_attempts,
                error=error,
            )
            return

        self._log_journal(
            row.correlation_id,
            event="attempt_failed",
            attempt_no=attempt_no,
            max_attempts=max_attempts,
            error=error,
        )
        delay = retry_delay_seconds(attempt_no)
        if delay > 0:
            self._log_journal(
                row.correlation_id,
                event="retry_scheduled",
                attempt_no=attempt_no,
                max_attempts=max_attempts,
                retry_after_seconds=delay,
            )

    def _log_journal(
        self,
        correlation_id: UUID,
        *,
        event: str,
        attempt_no: int | None = None,
        max_attempts: int | None = None,
        recipient_count: int | None = None,
        error: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        if self._journal is None:
            return

        if event == "enqueued":
            status = "email_enqueued"
            description = "Powiadomienie e-mail zakolejkowane."
            severity = KSeFSeverity.INFO
        elif event == "sent":
            status = "email_sent"
            description = "Powiadomienie e-mail wysłane."
            severity = KSeFSeverity.SUCCESS
        elif event == "attempt_failed":
            status = "email_attempt_failed"
            description = f"Powiadomienie e-mail: próba {attempt_no}/{max_attempts} nieudana."
            severity = KSeFSeverity.WARNING
        elif event == "retry_scheduled":
            status = "email_retry_scheduled"
            description = f"Powiadomienie e-mail: ponowienie za {retry_after_seconds}s."
            severity = KSeFSeverity.INFO
        elif event == "permanent_failure":
            status = "email_failed_permanent"
            description = f"Powiadomienie e-mail nie zostało wysłane po {max_attempts} próbach."
            severity = KSeFSeverity.WARNING
        else:
            status = "email_failed"
            description = "Powiadomienie e-mail nie zostało wysłane."
            severity = KSeFSeverity.WARNING

        metadata: dict = {"source": "purchase_sync_notify"}
        if attempt_no is not None and max_attempts is not None:
            metadata["attempt"] = attempt_no
            metadata["max_attempts"] = max_attempts
        if recipient_count is not None:
            metadata["recipient_count"] = recipient_count
        if retry_after_seconds is not None:
            metadata["retry_after"] = retry_after_seconds

        self._journal.log_event(
            operation_type=KSeFOperationType.PURCHASE_SYNC_EMAIL,
            severity=severity,
            status=status,
            short_description=description,
            correlation_id=correlation_id,
            error_message=error[:512] if error else None,
            metadata_json=metadata,
        )

    @staticmethod
    def _resolve_recipients() -> list[str]:
        return parse_notify_recipients(
            recipients_csv=settings.purchase_sync_notify_recipients,
            legacy_email=settings.purchase_sync_notify_email,
        )

    @staticmethod
    def _is_enabled() -> bool:
        return bool(settings.purchase_sync_notify_enabled)

    @staticmethod
    def _smtp_config() -> SmtpConfig | None:
        host = (settings.smtp_host or "").strip()
        from_addr = (settings.smtp_from or "").strip()
        if not host or not from_addr:
            return None
        return SmtpConfig(
            host=host,
            port=settings.smtp_port,
            user=(settings.smtp_user or "").strip() or None,
            password=(settings.smtp_password or "").strip() or None,
            from_addr=from_addr,
            use_tls=settings.smtp_use_tls,
        )
