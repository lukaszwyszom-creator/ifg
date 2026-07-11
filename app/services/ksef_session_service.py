from __future__ import annotations

import base64
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, ExternalServiceError, NotFoundError
from app.domain.enums import (
    InvoiceStatus,
    InvoiceType,
    KSeFOperationType,
    KSeFSeverity,
    PaymentMethod,
)
from app.domain.models.invoice import Invoice, InvoiceItem
from app.integrations.ksef.auth import KSeFAuthError, KSeFAuthProvider
from app.integrations.ksef.client import (
    KSeFClient,
    KSeFClientError,
    KSeFRateLimitDeferredError,
)
from app.integrations.ksef.xml_parser import parse_fa3_xml, purchase_items_validation_error
from app.persistence.models.ksef_session import KSeFSessionORM
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.ksef_sync_state_repository import KSeFSyncStateRepository
from app.services.ksef_purchase_auth_service import PurchaseAuthService
from app.services.ksef_purchase_sync_audit import (
    PurchaseSyncAudit,
    resolve_purchase_sync_window_details,
)
from app.services.purchase_sync_email_notifier import PurchaseSyncEmailNotifier
from app.services.ksef_token_store import (
    KEY_ACCESS_TOKEN,
    KEY_IV,
    KEY_REFRESH_TOKEN,
    KEY_REFRESH_VALID,
    KEY_SYMMETRIC_KEY,
    SESSION_ACTIVE,
    SESSION_AUTH_ACTIVE,
    SESSION_EXPIRED,
    SESSION_FAILED,
    SESSION_TERMINATED,
    TOKEN_CACHE_MARGIN,
    as_utc_aware,
    build_token_metadata,
    is_online_session,
    normalize_session_nip,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
_normalize_session_nip = normalize_session_nip
_as_utc_aware = as_utc_aware
_TOKEN_CACHE_MARGIN = TOKEN_CACHE_MARGIN
_KEY_ACCESS_TOKEN = KEY_ACCESS_TOKEN
_KEY_REFRESH_TOKEN = KEY_REFRESH_TOKEN
_KEY_REFRESH_VALID = KEY_REFRESH_VALID
_KEY_SYMMETRIC_KEY = KEY_SYMMETRIC_KEY
_KEY_IV = KEY_IV
_PROBE_ERROR_THRESHOLD = 3
_probe_cache_lock = threading.Lock()
_probe_cache: dict[str, dict[str, str | int | None]] = {}

_SCOPE_PURCHASE_INVOICES = "purchase_invoices"
_MAX_ERROR_SAMPLES = 5
_RATE_LIMIT_WARNING = (
    "KSeF ograniczył tempo pobierania faktur (HTTP 429). Część faktur nie została pobrana."
)
_PURCHASE_SYNC_NIP_LOCKS_GUARD = threading.Lock()
_purchase_sync_nip_locks: dict[str, threading.Lock] = {}


def _purchase_sync_lock_for(nip: str) -> threading.Lock:
    with _PURCHASE_SYNC_NIP_LOCKS_GUARD:
        if nip not in _purchase_sync_nip_locks:
            _purchase_sync_nip_locks[nip] = threading.Lock()
        return _purchase_sync_nip_locks[nip]


@dataclass
class KSeFSessionContext:
    """Kontekst potrzebny do operacji na fakturach w danej sesji KSeF."""

    access_token: str
    session_reference: str
    symmetric_key: bytes
    initialization_vector: bytes


class _TokenCacheEntry:
    __slots__ = ("token", "expires_at")

    def __init__(self, token: str, expires_at: datetime | None) -> None:
        self.token = token
        self.expires_at = expires_at

    def is_valid(self) -> bool:
        if self.expires_at is None:
            return True
        return datetime.now(UTC) < self.expires_at - _TOKEN_CACHE_MARGIN


class KSeFSessionService:
    def __init__(
        self,
        session: Session,
        auth_provider: KSeFAuthProvider,
        ksef_client: KSeFClient,
        audit_service: AuditService,
        invoice_repository: InvoiceRepository | None = None,
        journal_service=None,
        purchase_auth_service: PurchaseAuthService | None = None,
    ) -> None:
        self.session = session
        self.auth_provider = auth_provider
        self.ksef_client = ksef_client
        self.audit_service = audit_service
        self.invoice_repository = invoice_repository
        self._journal_service = journal_service
        self.purchase_auth = purchase_auth_service or PurchaseAuthService(
            session=session,
            auth_provider=auth_provider,
            audit_service=audit_service,
            journal_service=journal_service,
        )
        # cache tokenów — klucz: nip (str), wartość: _TokenCacheEntry
        self._token_cache: dict[str, _TokenCacheEntry] = {}
        self._cache_lock = threading.Lock()
        self._probe_cache_key = getattr(self.ksef_client, "_base_url", "default")

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def open_session(
        self, nip: str, actor_user_id: UUID | None = None
    ) -> KSeFSessionORM:
        nip = _normalize_session_nip(nip)
        if not nip:
            raise AppError("NIP sesji KSeF jest wymagany.")
        auth_token = settings.ksef_auth_token
        if not auth_token:
            raise AppError("KSEF_AUTH_TOKEN nie jest skonfigurowany.")

        active = self._get_active_online_session(nip)
        if active is not None:
            raise ConflictError(
                f"Istnieje już aktywna sesja KSeF dla NIP {nip}: "
                f"{active.session_reference}."
            )

        auth_only = self.purchase_auth._find_purchase_auth_record(nip)
        if auth_only is not None and auth_only.status == SESSION_AUTH_ACTIVE:
            purchase_ctx = self.purchase_auth.ensure_purchase_auth(nip, actor_user_id=actor_user_id)
            try:
                online_session = self.ksef_client.open_online_session(purchase_ctx.access_token)
            except KSeFClientError as exc:
                raise ExternalServiceError(f"Błąd otwarcia sesji KSeF: {exc}") from exc
            orm = auth_only
            orm.session_reference = online_session.session_reference
            orm.token_metadata_json = build_token_metadata(
                access_token=purchase_ctx.access_token,
                refresh_token=(orm.token_metadata_json or {}).get(KEY_REFRESH_TOKEN, ""),
                refresh_valid_until=None,
                symmetric_key=online_session.symmetric_key,
                initialization_vector=online_session.initialization_vector,
                existing=orm.token_metadata_json,
            )
            orm.status = SESSION_ACTIVE
            orm.updated_at = datetime.now(UTC)
            self.session.flush()
            self._invalidate_cache(nip)
            self.audit_service.record(
                actor_user_id=actor_user_id,
                actor_role="system",
                event_type="ksef_session.opened",
                entity_type="ksef_session",
                entity_id=str(orm.id),
                after={"status": SESSION_ACTIVE, "nip": nip, "upgraded_from": SESSION_AUTH_ACTIVE},
            )
            if self._journal_service is not None:
                self._journal_service.log_event(
                    operation_type=KSeFOperationType.SESSION_OPEN,
                    severity=KSeFSeverity.SUCCESS,
                    status="success",
                    short_description=f"Opened KSeF online session for NIP {nip} (upgraded purchase auth).",
                    correlation_id=orm.id,
                    metadata_json={"source": "session"},
                )
            return orm

        # 1. Uwierzytelnienie → access token + refresh token
        try:
            ksef_session = self.auth_provider.get_tokens(nip, auth_token)
        except KSeFAuthError as exc:
            raise ExternalServiceError(f"Błąd uwierzytelnienia KSeF: {exc}") from exc

        # 2. Otwarcie sesji interaktywnej → session reference + klucz symetryczny
        try:
            online_session = self.ksef_client.open_online_session(ksef_session.access_token)
        except KSeFClientError as exc:
            raise ExternalServiceError(f"Błąd otwarcia sesji KSeF: {exc}") from exc

        now = datetime.now(UTC)
        expires_at = ksef_session.access_valid_until

        orm = KSeFSessionORM(
            id=uuid4(),
            nip=nip,
            environment=self.auth_provider.environment,
            auth_method="token",
            session_reference=online_session.session_reference,
            token_metadata_json=build_token_metadata(
                access_token=ksef_session.access_token,
                refresh_token=ksef_session.refresh_token,
                refresh_valid_until=ksef_session.refresh_valid_until,
                symmetric_key=online_session.symmetric_key,
                initialization_vector=online_session.initialization_vector,
            ),
            status=SESSION_ACTIVE,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        self.session.add(orm)
        self.session.flush()

        # Unieważnij cache dla tego NIP po otwarciu nowej sesji
        self._invalidate_cache(nip)

        self.audit_service.record(
            actor_user_id=actor_user_id,
            actor_role="system",
            event_type="ksef_session.opened",
            entity_type="ksef_session",
            entity_id=str(orm.id),
            after={"status": SESSION_ACTIVE, "nip": nip},
        )
        if self._journal_service is not None:
            self._journal_service.log_event(
                operation_type=KSeFOperationType.SESSION_OPEN,
                severity=KSeFSeverity.SUCCESS,
                status="success",
                short_description=f"Opened KSeF session for NIP {nip}.",
                correlation_id=orm.id,
                metadata_json={"source": "session"},
            )

        return orm

    def get_active_session(self, nip: str) -> KSeFSessionORM:
        """Aktywna sesja online (wysyłka sprzedaży) — nie obejmuje samego purchase auth."""
        nip = normalize_session_nip(nip)
        orm = self._get_active_online_session(nip)
        if orm is None:
            raise NotFoundError(f"Brak aktywnej sesji KSeF dla NIP {nip}.")

        now = datetime.now(UTC)
        expires_at = _as_utc_aware(orm.expires_at)
        if expires_at is not None and expires_at <= now:
            orm.status = SESSION_EXPIRED
            self.session.flush()
            self._invalidate_cache(nip)
            if self._journal_service is not None:
                self._journal_service.log_event(
                    operation_type=KSeFOperationType.SESSION_EXPIRED,
                    severity=KSeFSeverity.WARNING,
                    status="expired",
                    short_description=f"KSeF session expired for NIP {nip}.",
                    correlation_id=orm.id,
                    metadata_json={"source": "session"},
                )
            raise NotFoundError(f"Sesja KSeF dla NIP {nip} wygasła.")

        return orm

    def ensure_online_session(self, nip: str) -> KSeFSessionContext:
        """Wymaga aktywnej sesji online FA(3) — używane przy wysyłce i pollingu sprzedaży."""
        return self.get_session_context(nip)

    def get_session_context(self, nip: str) -> KSeFSessionContext:
        """Zwraca pełny kontekst sesji online potrzebny do wysyłki faktur.

        Wynik access tokena jest cachowany (TTL = czas ważności − margines).
        """
        nip = normalize_session_nip(nip)
        with self._cache_lock:
            entry = self._token_cache.get(nip)
            if entry is not None and entry.is_valid():
                pass

        orm = self.get_active_session(nip)
        if not is_online_session(orm):
            raise NotFoundError(
                f"Brak aktywnej sesji online KSeF dla NIP {nip}. "
                "Otwórz sesję przez UI lub POST /api/v1/ksef-sessions/."
            )
        metadata = orm.token_metadata_json or {}
        access_token = metadata.get(_KEY_ACCESS_TOKEN)
        symmetric_key_b64 = metadata.get(_KEY_SYMMETRIC_KEY)
        iv_b64 = metadata.get(_KEY_IV)

        if not access_token or not symmetric_key_b64 or not iv_b64:
            raise AppError(
                f"Niekompletny kontekst sesji KSeF dla NIP {nip} — "
                "zainicjuj sesję ponownie."
            )

        with self._cache_lock:
            self._token_cache[nip] = _TokenCacheEntry(access_token, orm.expires_at)

        return KSeFSessionContext(
            access_token=access_token,
            session_reference=orm.session_reference or "",
            symmetric_key=base64.b64decode(symmetric_key_b64),
            initialization_vector=base64.b64decode(iv_b64),
        )

    def get_session_token(self, nip: str) -> str:
        """Zwraca access token dla danego NIP (alias dla wstecznej zgodności)."""
        return self.get_session_context(nip).access_token

    def close_session(
        self, nip: str, actor_user_id: UUID | None = None
    ) -> KSeFSessionORM:
        nip = _normalize_session_nip(nip)
        orm = self.get_active_session(nip)
        metadata = orm.token_metadata_json or {}
        access_token = metadata.get(_KEY_ACCESS_TOKEN, "")
        self.ksef_client.close_online_session(access_token, orm.session_reference or "")

        now = datetime.now(UTC)
        orm.status = SESSION_TERMINATED
        orm.updated_at = now
        self.session.flush()
        self._invalidate_cache(nip)

        self.audit_service.record(
            actor_user_id=actor_user_id,
            actor_role="system",
            event_type="ksef_session.closed",
            entity_type="ksef_session",
            entity_id=str(orm.id),
            after={"status": SESSION_TERMINATED, "nip": nip},
        )
        if self._journal_service is not None:
            self._journal_service.log_event(
                operation_type=KSeFOperationType.SESSION_CLOSE,
                severity=KSeFSeverity.INFO,
                status="success",
                short_description=f"Closed KSeF session for NIP {nip}.",
                correlation_id=orm.id,
                metadata_json={"source": "session"},
            )

        return orm

    def mark_session_expired(self, nip: str) -> None:
        """Oznacza aktywną sesję KSeF dla danego NIP jako wygasłą."""
        nip = _normalize_session_nip(nip)
        orm = self._get_active_online_session(nip)
        if orm is not None:
            orm.status = SESSION_EXPIRED
            orm.updated_at = datetime.now(UTC)
            self.session.flush()
            if self._journal_service is not None:
                self._journal_service.log_event(
                    operation_type=KSeFOperationType.SESSION_EXPIRED,
                    severity=KSeFSeverity.WARNING,
                    status="expired",
                    short_description=f"KSeF session marked expired for NIP {nip}.",
                    correlation_id=orm.id,
                    metadata_json={"source": "session"},
                )
        self._invalidate_cache(nip)

    def get_session_by_id(self, session_id: UUID) -> KSeFSessionORM:
        orm = self.session.get(KSeFSessionORM, session_id)
        if orm is None:
            raise NotFoundError(f"Nie znaleziono sesji KSeF {session_id}.")
        return orm

    def get_connection_status(self, nip: str | None) -> dict:
        probe_error = self._probe_connectivity_error()
        if probe_error is not None:
            return self._build_connection_status(
                ui_status="ERROR",
                reason=probe_error["reason"],
                has_session=False,
                last_error=probe_error["last_error"],
            )

        if not nip:
            return self._build_connection_status(
                ui_status="DISCONNECTED",
                reason="NO_SESSION",
                has_session=False,
            )

        nip = _normalize_session_nip(nip)
        if not nip:
            return self._build_connection_status(
                ui_status="DISCONNECTED",
                reason="NO_SESSION",
                has_session=False,
            )

        try:
            orm = self._get_active_online_session(nip)
            if orm is None:
                auth_record = self.purchase_auth._find_purchase_auth_record(nip)
                if auth_record is None or auth_record.status != SESSION_AUTH_ACTIVE:
                    return self._build_connection_status(
                        ui_status="DISCONNECTED",
                        reason="NO_SESSION",
                        has_session=False,
                    )
                from app.services.ksef_token_store import access_token_valid

                if not access_token_valid(auth_record):
                    return self._build_connection_status(
                        ui_status="DISCONNECTED",
                        reason="SESSION_EXPIRED",
                        has_session=False,
                    )
                return self._build_connection_status(
                    ui_status="CONNECTED",
                    reason="PURCHASE_AUTH_ONLY",
                    has_session=True,
                    session_expires_at=_as_utc_aware(auth_record.expires_at),
                )

            now = datetime.now(UTC)
            expires_at = _as_utc_aware(orm.expires_at)
            if expires_at is not None and expires_at <= now:
                orm.status = SESSION_EXPIRED
                orm.updated_at = now
                self.session.flush()
                self._invalidate_cache(nip)
                return self._build_connection_status(
                    ui_status="DISCONNECTED",
                    reason="SESSION_EXPIRED",
                    has_session=False,
                )

            return self._build_connection_status(
                ui_status="CONNECTED",
                reason="UNKNOWN",
                has_session=True,
                session_expires_at=expires_at,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("KSeF status check failed for NIP %s.", nip)
            return self._build_connection_status(
                ui_status="ERROR",
                reason="UNKNOWN",
                has_session=False,
                last_error=str(exc),
            )

    def expire_stale_sessions(self) -> int:
        now = datetime.now(UTC)
        stmt = select(KSeFSessionORM).where(
            KSeFSessionORM.status == SESSION_ACTIVE,
            KSeFSessionORM.expires_at <= now,
        )
        rows = self.session.scalars(stmt).all()
        for orm in rows:
            orm.status = SESSION_EXPIRED
            self._invalidate_cache(orm.nip)
        if rows:
            self.session.flush()
        return len(rows)

    # -------------------------------------------------------------------------
    # PURCHASE INVOICE SYNC
    # -------------------------------------------------------------------------

    @staticmethod
    def resolve_purchase_sync_window(
        date_from: date | None,
        date_to: date | None,
        *,
        days_back: int,
        force_full: bool,
        sync_state_json: dict | None,
        incremental: bool = False,
        resume_state: dict | None = None,
    ) -> tuple[date, date]:
        """Wylicza zakres dat zapytania KSeF (manualny lub inkrementalny)."""
        window = resolve_purchase_sync_window_details(
            date_from,
            date_to,
            days_back=days_back,
            force_full=force_full,
            sync_state_json=sync_state_json,
            incremental=incremental,
            overlap_days=settings.ksef_purchase_sync_overlap_days,
            full_days=settings.ksef_purchase_sync_full_days,
            resume_state=resume_state,
        )
        return window.date_from, window.date_to

    def find_active_purchase_sync_background_job(
        self,
        nip: str,
        *,
        exclude_job_id: UUID | None = None,
    ):
        """Zwraca pending/processing job sync zakupów dla NIP (opcjonalnie z wyłączeniem bieżącego)."""
        from app.persistence.models.background_job import BackgroundJob

        normalized = _normalize_session_nip(nip)
        if not normalized:
            return None
        stmt = (
            select(BackgroundJob)
            .where(
                BackgroundJob.job_type == "sync_purchase_invoices",
                BackgroundJob.status.in_(["pending", "processing"]),
                BackgroundJob.payload_json["nip"].astext == normalized,
            )
            .limit(1)
        )
        if exclude_job_id is not None:
            stmt = stmt.where(BackgroundJob.id != exclude_job_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def sync_purchase_invoices(
        self,
        *,
        nip: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        days_back: int | None = None,
        force_full: bool = False,
        incremental: bool = False,
        actor_user_id: UUID | None = None,
        resume_state: dict | None = None,
        exclude_job_id: UUID | None = None,
    ) -> dict:
        """Synchronizuje faktury zakupowe KSeF → lokalna baza z raportem parzystości."""
        resolved_nip = self._resolve_seller_nip(nip)
        active_job = self.find_active_purchase_sync_background_job(
            resolved_nip,
            exclude_job_id=exclude_job_id,
        )
        if active_job is not None:
            raise ConflictError(
                f"Synchronizacja zakupów KSeF już trwa dla NIP {resolved_nip} "
                f"(job_id={active_job.id}, status={active_job.status})."
            )

        nip_lock = _purchase_sync_lock_for(resolved_nip)
        if not nip_lock.acquire(blocking=False):
            raise ConflictError(
                f"Synchronizacja zakupów KSeF już trwa dla NIP {resolved_nip}."
            )

        resolved_days_back = (
            days_back if days_back is not None else settings.ksef_purchase_sync_days_back
        )

        sync_repo = KSeFSyncStateRepository(self.session)
        state = sync_repo.get_or_create(_SCOPE_PURCHASE_INVOICES)
        window = resolve_purchase_sync_window_details(
            date_from,
            date_to,
            days_back=resolved_days_back,
            force_full=force_full,
            sync_state_json=state.state_json,
            incremental=incremental,
            overlap_days=settings.ksef_purchase_sync_overlap_days,
            full_days=settings.ksef_purchase_sync_full_days,
            resume_state=resume_state,
        )
        resolved_from, resolved_to = window.date_from, window.date_to

        sync_repo.mark_running(_SCOPE_PURCHASE_INVOICES)
        audit = PurchaseSyncAudit(
            nip=resolved_nip,
            date_from=resolved_from,
            date_to=resolved_to,
        )
        audit.record_window(window)
        operation_type = (
            KSeFOperationType.PURCHASE_SYNC_AUTO
            if incremental and settings.ksef_auto_sync_enabled
            else KSeFOperationType.PURCHASE_SYNC_MANUAL
        )
        corr_id = uuid4()
        session_started_at = datetime.now(UTC)
        if self._journal_service is not None:
            self._journal_service.log_event(
                operation_type=operation_type,
                severity=KSeFSeverity.RUNNING,
                status="started",
                short_description="Purchase sync started.",
                correlation_id=corr_id,
                metadata_json={
                    "source": "auto" if operation_type == KSeFOperationType.PURCHASE_SYNC_AUTO else "manual",
                },
            )
            if resume_state:
                self._journal_service.log_event(
                    operation_type=KSeFOperationType.RESUME,
                    severity=KSeFSeverity.INFO,
                    status="resumed",
                    short_description="Purchase sync resumed from checkpoint.",
                    correlation_id=corr_id,
                    metadata_json={
                        "offset": resume_state.get("current_offset"),
                        "source": "resume_state",
                    },
                )
        prev_defer = self.ksef_client.defer_purchase_rate_limit
        self.ksef_client.defer_purchase_rate_limit = True
        try:
            counts = self.sync_received_invoices(
                nip=resolved_nip,
                date_from=resolved_from,
                date_to=resolved_to,
                actor_user_id=actor_user_id,
                resume_state=resume_state,
                audit=audit,
                correlation_id=corr_id,
            )
            self._finalize_purchase_sync_audit(
                audit, resolved_from, resolved_to, resolved_nip, correlation_id=corr_id
            )
            if counts.get("rate_limit_deferred"):
                warning = counts.get("warning") or _RATE_LIMIT_WARNING
                sync_repo.mark_error(_SCOPE_PURCHASE_INVOICES, warning)
                if self._journal_service is not None:
                    self._journal_service.log_event(
                        operation_type=KSeFOperationType.RETRY,
                        severity=KSeFSeverity.PAUSED,
                        status="deferred",
                        short_description="Purchase sync deferred due to KSeF 429.",
                        correlation_id=corr_id,
                        metadata_json={
                            "retry_after": counts["retry_after_seconds"],
                            "offset": (counts.get("resume_state") or {}).get("current_offset"),
                            "source": "ksef_429",
                        },
                    )
                return {
                    "status": "deferred",
                    "incomplete": True,
                    "date_from": resolved_from.isoformat(),
                    "date_to": resolved_to.isoformat(),
                    "subject_type": counts.get("subject_type"),
                    "ksef_returned": counts["received"],
                    "created": counts["saved"],
                    "skipped_existing": counts["skipped_existing"],
                    "errors": counts["skipped_parse"],
                    "error_samples": counts.get("error_samples", []),
                    "rate_limited": True,
                    "rate_limit_deferred": True,
                    "retry_after_seconds": counts["retry_after_seconds"],
                    "resume_state": counts["resume_state"],
                    "warning": warning,
                }
            report = {
                "status": "incomplete" if audit.is_sync_incomplete() else "ok",
                "date_from": resolved_from.isoformat(),
                "date_to": resolved_to.isoformat(),
                "subject_type": counts.get("subject_type"),
                "ksef_returned": counts["received"],
                "created": counts["saved"],
                "skipped_existing": counts["skipped_existing"],
                "errors": counts["skipped_parse"],
                "error_samples": counts.get("error_samples", []),
                "rate_limited": counts.get("rate_limited", False),
                "warning": counts.get("warning"),
                "incomplete": audit.is_sync_incomplete(),
            }
            if audit.is_sync_incomplete():
                sync_repo.mark_error(
                    _SCOPE_PURCHASE_INVOICES,
                    "KSeF purchase sync incomplete — see KSEF_PURCHASE_SYNC_AUDIT logs",
                )
            else:
                sync_repo.mark_success(
                    _SCOPE_PURCHASE_INVOICES,
                    state_json={
                        "last_date_from": resolved_from.isoformat(),
                        "last_date_to": resolved_to.isoformat(),
                        "last_subject_type": counts.get("subject_type"),
                        "last_counts": report,
                    },
                )
            logger.info(
                "KSeF purchases sync done: status=%s incremental=%s date_from=%s date_to=%s subjectType=%s "
                "ksef_returned=%d created=%d skipped_existing=%d errors=%d incomplete=%s",
                report["status"],
                incremental,
                resolved_from,
                resolved_to,
                report["subject_type"],
                report["ksef_returned"],
                report["created"],
                report["skipped_existing"],
                report["errors"],
                report["incomplete"],
            )
            if self._journal_service is not None:
                self._journal_service.log_event(
                    operation_type=operation_type,
                    severity=KSeFSeverity.WARNING if report["incomplete"] else KSeFSeverity.SUCCESS,
                    status=report["status"],
                    short_description="Purchase sync finished.",
                    correlation_id=corr_id,
                    metadata_json={
                        "downloaded": report["ksef_returned"],
                        "saved": report["created"],
                        "duplicates": report["skipped_existing"],
                        "skipped": report["errors"],
                        "source": "auto" if operation_type == KSeFOperationType.PURCHASE_SYNC_AUTO else "manual",
                    },
                )
            if not audit.is_sync_incomplete() and report["status"] == "ok":
                PurchaseSyncEmailNotifier(
                    self.session,
                    journal_service=self._journal_service,
                ).maybe_enqueue_after_sync(
                    correlation_id=corr_id,
                    operation_type=operation_type,
                    audit=audit,
                    started_at=session_started_at,
                    finished_at=datetime.now(UTC),
                )
            return report
        except Exception as exc:
            if audit.is_sync_incomplete():
                audit.emit_full_report()
            sync_repo.mark_error(_SCOPE_PURCHASE_INVOICES, str(exc))
            if self._journal_service is not None:
                self._journal_service.log_event(
                    operation_type=KSeFOperationType.ERROR,
                    severity=KSeFSeverity.ERROR,
                    status="failed",
                    short_description="Purchase sync failed.",
                    correlation_id=corr_id,
                    error_message=str(exc)[:512],
                    metadata_json={"error_code": "PURCHASE_SYNC_ERROR", "source": "sync"},
                )
            raise
        finally:
            self.ksef_client.defer_purchase_rate_limit = prev_defer
            nip_lock.release()

    def _finalize_purchase_sync_audit(
        self,
        audit: PurchaseSyncAudit,
        date_from: date,
        date_to: date,
        nip: str,
        correlation_id: UUID | None = None,
    ) -> None:
        if self.invoice_repository is not None:
            audit.db_refs_in_window = set(
                self.invoice_repository.list_ksef_purchase_refs_in_issue_range(
                    date_from,
                    date_to,
                    buyer_nip=nip,
                )
            )
            audit.final_database_count = len(audit.db_refs_in_window)
        audit.emit_full_report()
        if self._journal_service is not None:
            self._journal_service.log_event(
                operation_type=KSeFOperationType.PURCHASE_IMPORT_SUMMARY,
                severity=KSeFSeverity.INFO,
                status="summary",
                short_description="Purchase import summary emitted.",
                correlation_id=correlation_id or uuid4(),
                metadata_json={
                    "downloaded": audit.xml_downloaded,
                    "saved": audit.saved,
                    "duplicates": audit.skipped_existing,
                    "skipped": audit.skipped_invalid + audit.skipped_error,
                    "source": "audit_summary",
                },
            )

    def sync_received_invoices(
        self,
        nip: str,
        date_from: date,
        date_to: date,
        actor_user_id: UUID | None = None,
        resume_state: dict | None = None,
        audit: PurchaseSyncAudit | None = None,
        correlation_id: UUID | None = None,
    ) -> dict:
        """Pobiera faktury zakupowe z KSeF (incremental + resume przy HTTP 429)."""
        if self.invoice_repository is None:
            raise AppError("InvoiceRepository nie jest skonfigurowane w KSeFSessionService.")

        auth_ctx = self.purchase_auth.ensure_purchase_auth(nip, actor_user_id=actor_user_id)
        if audit is not None:
            audit.sync_path = "incremental"
        return self._sync_received_invoices_incremental(
            nip=nip,
            access_token=auth_ctx.access_token,
            date_from=date_from,
            date_to=date_to,
            actor_user_id=actor_user_id,
            resume_state=resume_state,
            audit=audit,
            correlation_id=correlation_id,
        )

    def _sync_received_invoices_incremental(
        self,
        *,
        nip: str,
        access_token: str,
        date_from: date,
        date_to: date,
        actor_user_id: UUID | None,
        resume_state: dict | None,
        audit: PurchaseSyncAudit | None = None,
        correlation_id: UUID | None = None,
    ) -> dict:
        """Pobiera metadata raz, następnie GET+save per faktura z resume przy 429."""
        resume = resume_state or {}
        refs: list[str] | None = resume.get("invoice_refs")
        start_offset = int(resume.get("current_offset", 0))
        subject_type_used: str | None = resume.get("subject_type")
        saved = int(resume.get("saved_accumulated", 0))
        skipped_existing = int(resume.get("skipped_existing_accumulated", 0))
        skipped_parse = int(resume.get("skipped_parse_accumulated", 0))
        error_samples: list[str] = list(resume.get("error_samples", []))[:_MAX_ERROR_SAMPLES]

        if not refs:
            metadata_refs = self.ksef_client.query_purchase_metadata_refs(
                access_token=access_token,
                date_from=date_from.isoformat(),
                date_to=date_to.isoformat(),
                audit=audit,
            )
            if metadata_refs is None:
                raise ExternalServiceError(
                    "Endpoint metadata KSeF niedostępny — synchronizacja zakupów wymaga "
                    "POST /invoices/query/metadata."
                )
            refs = metadata_refs
            subject_type_used = "subject2"
            start_offset = 0
            if self._journal_service is not None:
                self._journal_service.log_event(
                    operation_type=KSeFOperationType.PURCHASE_METADATA_FETCH,
                    severity=KSeFSeverity.INFO,
                    status="success",
                    short_description="Fetched purchase metadata references.",
                    correlation_id=correlation_id or uuid4(),
                    metadata_json={
                        "downloaded": len(refs),
                        "source": "metadata",
                    },
                )
        elif audit is not None and audit.invoice_ids_received == 0:
            audit.invoice_ids_received = len(refs)
            audit.metadata_returned = len(refs)

        if audit is not None and audit.metadata_returned == 0 and refs:
            audit.finalize_metadata(refs)

        logger.info(
            "KSeF purchases incremental sync subjectType=%s refs=%d offset=%d date_from=%s date_to=%s",
            subject_type_used,
            len(refs),
            start_offset,
            date_from,
            date_to,
        )

        for idx in range(start_offset, len(refs)):
            ref = refs[idx]
            if self.invoice_repository.exists_by_ksef_number(ref):
                if audit is not None:
                    audit.record_skipped_existing(ref)
                skipped_existing += 1
                self.session.flush()
                continue
            try:
                xml_bytes = self.ksef_client.get_purchase_invoice_xml(access_token, ref)
                if audit is not None:
                    audit.record_xml_downloaded(ref)
                if self._journal_service is not None:
                    self._journal_service.log_event(
                        operation_type=KSeFOperationType.PURCHASE_INVOICE_FETCH,
                        severity=KSeFSeverity.INFO,
                        status="downloaded",
                        short_description="Fetched purchase invoice XML.",
                        correlation_id=correlation_id or uuid4(),
                        ksef_reference_number=ref,
                        metadata_json={"source": "purchase_fetch"},
                    )
            except KSeFRateLimitDeferredError as exc:
                if audit is not None:
                    audit.rate_limited = True
                    audit.incomplete = True
                self.session.flush()
                return {
                    "received": len(refs),
                    "saved": saved,
                    "skipped_existing": skipped_existing,
                    "skipped_parse": skipped_parse,
                    "subject_type": subject_type_used,
                    "error_samples": error_samples,
                    "rate_limited": True,
                    "rate_limit_deferred": True,
                    "retry_after_seconds": exc.retry_after_seconds,
                    "resume_state": {
                        "invoice_refs": refs,
                        "current_offset": idx,
                        "current_reference": ref,
                        "downloaded_count": idx,
                        "subject_type": subject_type_used,
                        "saved_accumulated": saved,
                        "skipped_existing_accumulated": skipped_existing,
                        "skipped_parse_accumulated": skipped_parse,
                        "error_samples": error_samples,
                    },
                    "warning": _RATE_LIMIT_WARNING,
                }
            except KSeFClientError as exc:
                raise ExternalServiceError(f"Błąd synchronizacji z KSeF: {exc}") from exc

            outcome = self._process_purchase_invoice_xml(
                ksef_reference_number=ref,
                xml_bytes=xml_bytes,
                actor_user_id=actor_user_id,
                error_samples=error_samples,
                audit=audit,
            )
            if outcome == "saved":
                saved += 1
            elif outcome == "skipped_existing":
                skipped_existing += 1
            else:
                skipped_parse += 1
            self.session.flush()

        return {
            "received": len(refs),
            "saved": saved,
            "skipped_existing": skipped_existing,
            "skipped_parse": skipped_parse,
            "subject_type": subject_type_used,
            "error_samples": error_samples,
            "rate_limited": False,
            "rate_limit_deferred": False,
        }

    def _process_purchase_invoice_xml(
        self,
        *,
        ksef_reference_number: str,
        xml_bytes: bytes,
        actor_user_id: UUID | None,
        error_samples: list[str],
        audit: PurchaseSyncAudit | None = None,
    ) -> str:
        """Import pojedynczej faktury zakupowej. Zwraca saved|skipped_existing|skipped_parse."""
        if self.invoice_repository.exists_by_ksef_number(ksef_reference_number):
            logger.debug("KSeF sync: pomijam istniejącą fakturę %s", ksef_reference_number)
            if audit is not None:
                audit.record_skipped_existing(ksef_reference_number)
            return "skipped_existing"

        try:
            parsed = parse_fa3_xml(xml_bytes)
        except (ValueError, Exception) as exc:  # noqa: BLE001
            logger.warning("KSeF sync: błąd parsowania %s: %s", ksef_reference_number, exc)
            if len(error_samples) < _MAX_ERROR_SAMPLES:
                error_samples.append(
                    f"{ksef_reference_number}: parse error: {str(exc)[:120]}"
                )
            if audit is not None:
                audit.record_skipped_invalid(ksef_reference_number)
            return "skipped_parse"

        items_error = purchase_items_validation_error(parsed)
        if items_error:
            logger.error(
                "KSeF sync: faktura %s (nr=%s) — %s — pomijam zapis",
                ksef_reference_number,
                parsed.get("number_local"),
                items_error,
            )
            if len(error_samples) < _MAX_ERROR_SAMPLES:
                error_samples.append(f"{ksef_reference_number}: {items_error[:120]}")
            if audit is not None:
                audit.record_skipped_invalid(ksef_reference_number)
            return "skipped_parse"

        try:
            invoice_type_str = parsed.get("invoice_type", "VAT")
            try:
                invoice_type = InvoiceType(invoice_type_str)
            except ValueError:
                invoice_type = InvoiceType.VAT

            exchange_rate = parsed.get("exchange_rate")
            exchange_rate_date_str = parsed.get("exchange_rate_date")
            exchange_rate_date: date | None = None
            if exchange_rate_date_str:
                try:
                    exchange_rate_date = date.fromisoformat(exchange_rate_date_str)
                except ValueError:
                    pass

            items = [
                InvoiceItem(
                    name=item["name"] or "",
                    quantity=Decimal(str(item["quantity"])),
                    unit=item["unit"] or "szt.",
                    unit_price_net=Decimal(str(item["unit_price_net"])),
                    vat_rate=Decimal(str(item["vat_rate"])),
                    net_total=Decimal(str(item["net_total"])),
                    vat_total=Decimal(str(item["vat_total"])),
                    gross_total=Decimal(str(item["gross_total"])),
                    sort_order=item["sort_order"],
                )
                for item in parsed.get("items", [])
            ]

            now = datetime.now(UTC)
            invoice = Invoice(
                id=uuid4(),
                status=InvoiceStatus.ACCEPTED,
                issue_date=date.fromisoformat(parsed["issue_date"]),
                sale_date=date.fromisoformat(parsed["sale_date"]),
                due_date=date.fromisoformat(parsed["due_date"]) if parsed.get("due_date") else None,
                payment_method=PaymentMethod(parsed["payment_method"])
                if parsed.get("payment_method") in {"cash", "transfer"}
                else PaymentMethod.TRANSFER,
                currency=parsed.get("currency", "PLN"),
                seller_snapshot=parsed["seller_snapshot"],
                buyer_snapshot=parsed["buyer_snapshot"],
                items=items,
                total_net=Decimal(str(parsed.get("total_net", 0))),
                total_vat=Decimal(str(parsed.get("total_vat", 0))),
                total_gross=Decimal(str(parsed.get("total_gross", 0))),
                created_at=now,
                updated_at=now,
                number_local=parsed.get("number_local"),
                ksef_reference_number=ksef_reference_number,
                invoice_type=invoice_type,
                use_split_payment=parsed.get("use_split_payment", False),
                self_billing=parsed.get("self_billing", False),
                reverse_charge=parsed.get("reverse_charge", False),
                reverse_charge_art=parsed.get("reverse_charge_art", False),
                reverse_charge_flag=parsed.get("reverse_charge_flag", False),
                cash_accounting_method=parsed.get("cash_accounting_method", False),
                exchange_rate=exchange_rate,
                exchange_rate_date=exchange_rate_date,
                direction="purchase",
                created_by=actor_user_id,
            )

            self.invoice_repository.add(invoice, source_system="ksef_import")
            logger.info("KSeF sync: zapisano fakturę zakupową %s", ksef_reference_number)
            if audit is not None:
                audit.record_saved(ksef_reference_number, invoice_id=invoice.id)
            return "saved"
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "KSeF sync: błąd tworzenia faktury %s: %s",
                ksef_reference_number,
                exc,
                exc_info=True,
            )
            if len(error_samples) < _MAX_ERROR_SAMPLES:
                error_samples.append(
                    f"{ksef_reference_number}: import error: {str(exc)[:120]}"
                )
            if audit is not None:
                audit.record_skipped_error(ksef_reference_number)
            return "skipped_parse"

    def _resolve_seller_nip(self, requested_nip: str | None = None) -> str:
        requested_nip = _normalize_session_nip(requested_nip)
        if requested_nip:
            return requested_nip

        seller_nip = _normalize_session_nip(settings.seller_nip)
        if not seller_nip:
            raise AppError("Brak NIP właściciela aplikacji w konfiguracji.")
        return seller_nip

    @staticmethod
    def resolve_invoice_seller_nip(invoice: Invoice | None) -> str:
        """NIP sprzedawcy do operacji KSeF (poll/submit) — snapshot lub settings."""
        snap = (getattr(invoice, "seller_snapshot", None) or {}) if invoice else {}
        nip = _normalize_session_nip(str(snap.get("nip") or ""))
        if nip:
            return nip
        return _normalize_session_nip(settings.seller_nip)

    # -------------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------------

    def _get_active_online_session(self, nip: str) -> KSeFSessionORM | None:
        normalized = normalize_session_nip(nip)
        if not normalized:
            return None
        stmt = (
            select(KSeFSessionORM)
            .where(
                KSeFSessionORM.nip == normalized,
                KSeFSessionORM.status == SESSION_ACTIVE,
                KSeFSessionORM.session_reference.is_not(None),
                KSeFSessionORM.environment == self.auth_provider.environment,
            )
            .order_by(KSeFSessionORM.created_at.desc())
            .limit(1)
        )
        orm = self.session.execute(stmt).scalar_one_or_none()
        if orm is not None:
            return orm
        fallback = (
            select(KSeFSessionORM)
            .where(
                KSeFSessionORM.nip == normalized,
                KSeFSessionORM.status == SESSION_ACTIVE,
                KSeFSessionORM.session_reference.is_not(None),
            )
            .order_by(KSeFSessionORM.created_at.desc())
            .limit(1)
        )
        return self.session.execute(fallback).scalar_one_or_none()

    def _get_active_db_session(self, nip: str) -> KSeFSessionORM | None:
        """Backward-compatible alias — zwraca wyłącznie sesję online."""
        return self._get_active_online_session(nip)

    @staticmethod
    def _build_connection_status(
        ui_status: str,
        reason: str,
        has_session: bool,
        session_expires_at: datetime | None = None,
        last_error: str | None = None,
    ) -> dict:
        return {
            "ui_status": ui_status,
            "details": {
                "reason": reason,
                "has_session": has_session,
                "session_expires_at": session_expires_at,
                "last_error": last_error,
            },
        }

    @staticmethod
    def _map_status_reason_from_client_error(exc: KSeFClientError) -> str:
        if exc.status_code in (401, 403):
            return "AUTH_ERROR"
        if exc.transient and exc.status_code is None:
            return "NETWORK_ERROR"
        if exc.transient:
            return "KSEF_UNAVAILABLE"
        return "UNKNOWN"

    def _invalidate_cache(self, nip: str) -> None:
        with self._cache_lock:
            self._token_cache.pop(nip, None)

    def _probe_connectivity_error(self) -> dict | None:
        try:
            self.ksef_client.check_connectivity()
        except KSeFClientError as exc:
            reason = self._map_status_reason_from_client_error(exc)
            with _probe_cache_lock:
                state = _probe_cache.setdefault(
                    self._probe_cache_key,
                    {"failure_count": 0, "last_error": None, "last_reason": "UNKNOWN"},
                )
                state["failure_count"] = int(state["failure_count"] or 0) + 1
                state["last_error"] = str(exc)
                state["last_reason"] = reason
                if int(state["failure_count"]) < _PROBE_ERROR_THRESHOLD:
                    logger.warning(
                        "KSeF connectivity probe failed (%s/%s): %s",
                        state["failure_count"],
                        _PROBE_ERROR_THRESHOLD,
                        exc,
                    )
                    return None
                return {
                    "reason": str(state["last_reason"]),
                    "last_error": str(state["last_error"]),
                }
        except Exception as exc:  # noqa: BLE001
            logger.exception("KSeF connectivity probe failed.")
            with _probe_cache_lock:
                state = _probe_cache.setdefault(
                    self._probe_cache_key,
                    {"failure_count": 0, "last_error": None, "last_reason": "UNKNOWN"},
                )
                state["failure_count"] = int(state["failure_count"] or 0) + 1
                state["last_error"] = str(exc)
                state["last_reason"] = "UNKNOWN"
                if int(state["failure_count"]) < _PROBE_ERROR_THRESHOLD:
                    return None
                return {
                    "reason": str(state["last_reason"]),
                    "last_error": str(state["last_error"]),
                }

        with _probe_cache_lock:
            _probe_cache[self._probe_cache_key] = {
                "failure_count": 0,
                "last_error": None,
                "last_reason": "UNKNOWN",
            }
        return None
