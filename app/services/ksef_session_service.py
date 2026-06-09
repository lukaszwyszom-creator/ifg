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
from app.domain.enums import InvoiceStatus, InvoiceType, PaymentMethod
from app.domain.models.invoice import Invoice, InvoiceItem
from app.integrations.ksef.auth import KSeFAuthError, KSeFAuthProvider
from app.integrations.ksef.client import KSeFClient, KSeFClientError
from app.integrations.ksef.xml_parser import parse_fa3_xml
from app.persistence.models.ksef_session import KSeFSessionORM
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.ksef_sync_state_repository import KSeFSyncStateRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

SESSION_ACTIVE = "active"
SESSION_TERMINATED = "terminated"
SESSION_EXPIRED = "expired"
SESSION_FAILED = "failed"
_SCOPE_PURCHASE_INVOICES = "purchase_invoices"
_MAX_ERROR_SAMPLES = 5

# Margines przed wygaśnięciem — token uznajemy za ważny jeśli trwa > MARGIN
_TOKEN_CACHE_MARGIN = timedelta(seconds=30)

# Klucze w token_metadata_json
_KEY_ACCESS_TOKEN = "access_token"
_KEY_REFRESH_TOKEN = "refresh_token"
_KEY_REFRESH_VALID = "refresh_valid_until"
_KEY_SYMMETRIC_KEY = "symmetric_key"
_KEY_IV = "initialization_vector"
_PROBE_ERROR_THRESHOLD = 3
_probe_cache_lock = threading.Lock()
_probe_cache: dict[str, dict[str, str | int | None]] = {}


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
    ) -> None:
        self.session = session
        self.auth_provider = auth_provider
        self.ksef_client = ksef_client
        self.audit_service = audit_service
        self.invoice_repository = invoice_repository
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
        auth_token = settings.ksef_auth_token
        if not auth_token:
            raise AppError("KSEF_AUTH_TOKEN nie jest skonfigurowany.")

        active = self._get_active_db_session(nip)
        if active is not None:
            raise ConflictError(
                f"Istnieje już aktywna sesja KSeF dla NIP {nip}: "
                f"{active.session_reference}."
            )

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
            token_metadata_json={
                _KEY_ACCESS_TOKEN: ksef_session.access_token,
                _KEY_REFRESH_TOKEN: ksef_session.refresh_token,
                _KEY_REFRESH_VALID: (
                    ksef_session.refresh_valid_until.isoformat()
                    if ksef_session.refresh_valid_until else None
                ),
                _KEY_SYMMETRIC_KEY: base64.b64encode(online_session.symmetric_key).decode("ascii"),
                _KEY_IV: base64.b64encode(online_session.initialization_vector).decode("ascii"),
            },
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

        return orm

    def get_active_session(self, nip: str) -> KSeFSessionORM:
        orm = self._get_active_db_session(nip)
        if orm is None:
            raise NotFoundError(f"Brak aktywnej sesji KSeF dla NIP {nip}.")

        now = datetime.now(UTC)
        if orm.expires_at is not None and orm.expires_at <= now:
            orm.status = SESSION_EXPIRED
            self.session.flush()
            self._invalidate_cache(nip)
            raise NotFoundError(f"Sesja KSeF dla NIP {nip} wygasła.")

        return orm

    def get_session_context(self, nip: str) -> KSeFSessionContext:
        """Zwraca pełny kontekst sesji potrzebny do wysyłki faktur.

        Wynik access tokena jest cachowany (TTL = czas ważności − margines).
        """
        with self._cache_lock:
            entry = self._token_cache.get(nip)
            if entry is not None and entry.is_valid():
                # Cache ma tylko access_token — pełny kontekst musi być z DB
                pass

        orm = self.get_active_session(nip)
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

        return orm

    def mark_session_expired(self, nip: str) -> None:
        """Oznacza aktywną sesję KSeF dla danego NIP jako wygasłą."""
        orm = self._get_active_db_session(nip)
        if orm is not None:
            orm.status = SESSION_EXPIRED
            orm.updated_at = datetime.now(UTC)
            self.session.flush()
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

        try:
            orm = self._get_active_db_session(nip)
            if orm is None:
                return self._build_connection_status(
                    ui_status="DISCONNECTED",
                    reason="NO_SESSION",
                    has_session=False,
                )

            now = datetime.now(UTC)
            if orm.expires_at is not None and orm.expires_at <= now:
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
                session_expires_at=orm.expires_at,
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
    ) -> tuple[date, date]:
        """Wylicza zakres dat zapytania KSeF (inkrementalny lub pełny)."""
        resolved_to = date_to or datetime.now(UTC).date()
        if date_from is not None:
            return date_from, resolved_to

        if force_full:
            return resolved_to - timedelta(days=settings.ksef_purchase_sync_full_days), resolved_to

        if sync_state_json:
            last_date_to_raw = sync_state_json.get("last_date_to")
            if isinstance(last_date_to_raw, str):
                try:
                    last_date_to = date.fromisoformat(last_date_to_raw)
                    incremental_from = last_date_to - timedelta(
                        days=settings.ksef_purchase_sync_overlap_days
                    )
                    default_from = resolved_to - timedelta(days=days_back)
                    return max(default_from, incremental_from), resolved_to
                except ValueError:
                    pass

        return resolved_to - timedelta(days=days_back), resolved_to

    def sync_purchase_invoices(
        self,
        *,
        nip: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        days_back: int | None = None,
        force_full: bool = False,
        actor_user_id: UUID | None = None,
    ) -> dict:
        """Synchronizuje faktury zakupowe KSeF → lokalna baza z raportem parzystości."""
        resolved_nip = self._resolve_seller_nip(nip)
        resolved_days_back = (
            days_back if days_back is not None else settings.ksef_purchase_sync_days_back
        )

        sync_repo = KSeFSyncStateRepository(self.session)
        state = sync_repo.get_or_create(_SCOPE_PURCHASE_INVOICES)
        resolved_from, resolved_to = self.resolve_purchase_sync_window(
            date_from,
            date_to,
            days_back=resolved_days_back,
            force_full=force_full,
            sync_state_json=state.state_json,
        )

        sync_repo.mark_running(_SCOPE_PURCHASE_INVOICES)
        try:
            counts = self.sync_received_invoices(
                nip=resolved_nip,
                date_from=resolved_from,
                date_to=resolved_to,
                actor_user_id=actor_user_id,
            )
            report = {
                "status": "ok",
                "date_from": resolved_from.isoformat(),
                "date_to": resolved_to.isoformat(),
                "subject_type": counts.get("subject_type"),
                "ksef_returned": counts["received"],
                "created": counts["saved"],
                "skipped_existing": counts["skipped_existing"],
                "errors": counts["skipped_parse"],
                "error_samples": counts.get("error_samples", []),
            }
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
                "KSeF purchases sync done: date_from=%s date_to=%s subjectType=%s "
                "ksef_returned=%d created=%d skipped_existing=%d errors=%d",
                resolved_from,
                resolved_to,
                report["subject_type"],
                report["ksef_returned"],
                report["created"],
                report["skipped_existing"],
                report["errors"],
            )
            return report
        except Exception as exc:
            sync_repo.mark_error(_SCOPE_PURCHASE_INVOICES, str(exc))
            raise

    def sync_received_invoices(
        self,
        nip: str,
        date_from: date,
        date_to: date,
        actor_user_id: UUID | None = None,
    ) -> dict:
        """Pobiera faktury zakupowe z KSeF za podany zakres dat i zapisuje nowe do bazy.

        Wymaga aktywnej sesji KSeF dla podanego NIP.
        Pomija faktury już istniejące w bazie (identyfikacja po ksefReferenceNumber).
        Zwraca słownik: {received, saved, skipped_existing, skipped_parse, subject_type, error_samples}.
        """
        if self.invoice_repository is None:
            raise AppError("InvoiceRepository nie jest skonfigurowane w KSeFSessionService.")

        ctx = self.get_session_context(nip)

        received = []
        subject_type_used: str | None = None
        for subject_type in ("subject2", "subject1", "subject3"):
            try:
                batch = self.ksef_client.query_received_invoices(
                    access_token=ctx.access_token,
                    session_reference=ctx.session_reference,
                    symmetric_key=ctx.symmetric_key,
                    iv=ctx.initialization_vector,
                    invoicing_date_from=date_from.isoformat(),
                    invoicing_date_to=date_to.isoformat(),
                    subject_type=subject_type,
                )
            except KSeFClientError as exc:
                raise ExternalServiceError(f"Błąd synchronizacji z KSeF: {exc}") from exc

            logger.info(
                "KSeF purchases sync subjectType=%s result_count=%d date_from=%s date_to=%s",
                subject_type,
                len(batch),
                date_from,
                date_to,
            )
            subject_type_used = subject_type
            if batch:
                received = batch
                break

        saved = 0
        skipped_existing = 0
        skipped_parse = 0
        error_samples: list[str] = []
        for result in received:
            if self.invoice_repository.exists_by_ksef_number(result.ksef_reference_number):
                logger.debug("KSeF sync: pomijam istniejącą fakturę %s", result.ksef_reference_number)
                skipped_existing += 1
                continue
            try:
                parsed = parse_fa3_xml(result.xml_bytes)
            except (ValueError, Exception) as exc:  # noqa: BLE001
                logger.warning("KSeF sync: błąd parsowania %s: %s", result.ksef_reference_number, exc)
                skipped_parse += 1
                if len(error_samples) < _MAX_ERROR_SAMPLES:
                    error_samples.append(
                        f"{result.ksef_reference_number}: parse error: {str(exc)[:120]}"
                    )
                continue

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
                        from datetime import date as _date
                        exchange_rate_date = _date.fromisoformat(exchange_rate_date_str)
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
                    ksef_reference_number=result.ksef_reference_number,
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
                saved += 1
                logger.info("KSeF sync: zapisano fakturę zakupową %s", result.ksef_reference_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "KSeF sync: błąd tworzenia faktury %s: %s",
                    result.ksef_reference_number,
                    exc,
                    exc_info=True,
                )
                skipped_parse += 1
                if len(error_samples) < _MAX_ERROR_SAMPLES:
                    error_samples.append(
                        f"{result.ksef_reference_number}: import error: {str(exc)[:120]}"
                    )

        return {
            "received": len(received),
            "saved": saved,
            "skipped_existing": skipped_existing,
            "skipped_parse": skipped_parse,
            "subject_type": subject_type_used,
            "error_samples": error_samples,
        }

    def _resolve_seller_nip(self, requested_nip: str | None = None) -> str:
        requested_nip = (requested_nip or "").strip()
        if requested_nip:
            return requested_nip

        seller_nip = (settings.seller_nip or "").strip()
        if not seller_nip:
            raise AppError("Brak NIP właściciela aplikacji w konfiguracji.")
        return seller_nip

    # -------------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------------

    def _get_active_db_session(self, nip: str) -> KSeFSessionORM | None:
        stmt = select(KSeFSessionORM).where(
            KSeFSessionORM.nip == nip,
            KSeFSessionORM.status == SESSION_ACTIVE,
        )
        return self.session.execute(stmt).scalar_one_or_none()

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
