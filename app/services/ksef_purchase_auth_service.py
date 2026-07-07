from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, ExternalServiceError
from app.domain.enums import KSeFOperationType, KSeFSeverity
from app.integrations.ksef.auth import KSeFAuthError, KSeFAuthProvider, KSeFSession
from app.persistence.models.ksef_session import KSeFSessionORM
from app.services.ksef_token_store import (
    KEY_ACCESS_TOKEN,
    SESSION_ACTIVE,
    SESSION_AUTH_ACTIVE,
    access_token_valid,
    as_utc_aware,
    build_token_metadata,
    is_online_session,
    normalize_session_nip,
    refresh_token_valid,
)

logger = logging.getLogger(__name__)

_PURCHASE_AUTH_STATUSES = (SESSION_ACTIVE, SESSION_AUTH_ACTIVE)


@dataclass(frozen=True, slots=True)
class PurchaseAuthContext:
    """Ważny access token do operacji zakupowych KSeF (metadata + download XML)."""

    nip: str
    access_token: str
    expires_at: datetime | None
    record_id: UUID
    auth_method: str = "token"


class PurchaseAuthService:
    """Zarządza cyklem życia tokenów KSeF wyłącznie dla synchronizacji zakupów."""

    def __init__(
        self,
        session: Session,
        auth_provider: KSeFAuthProvider,
        *,
        audit_service=None,
        journal_service=None,
    ) -> None:
        self.session = session
        self.auth_provider = auth_provider
        self.audit_service = audit_service
        self._journal_service = journal_service

    def ensure_purchase_auth(
        self,
        nip: str,
        *,
        actor_user_id: UUID | None = None,
    ) -> PurchaseAuthContext:
        """Zwraca ważny access token — refresh lub pełna autoryzacja bez sesji online."""
        normalized = normalize_session_nip(nip)
        if not normalized:
            raise AppError("NIP sesji KSeF jest wymagany.")

        record = self._find_purchase_auth_record(normalized)
        if record is not None and access_token_valid(record):
            return self._to_context(record)

        if record is not None and refresh_token_valid(record):
            try:
                return self._refresh_tokens(record, actor_user_id=actor_user_id)
            except KSeFAuthError as exc:
                logger.warning(
                    "KSeF purchase auth refresh failed for NIP %s: %s — falling back to full auth",
                    normalized,
                    exc,
                )
                self._journal(
                    operation_type=KSeFOperationType.SESSION_REFRESH,
                    severity=KSeFSeverity.WARNING,
                    status="refresh_failed",
                    nip=normalized,
                    correlation_id=record.id,
                    message=str(exc)[:240],
                )

        return self._authenticate_fresh(
            normalized,
            actor_user_id=actor_user_id,
            existing=record,
        )

    def get_purchase_access_token(self, nip: str, *, actor_user_id: UUID | None = None) -> str:
        return self.ensure_purchase_auth(nip, actor_user_id=actor_user_id).access_token

    def _authenticate_fresh(
        self,
        nip: str,
        *,
        actor_user_id: UUID | None,
        existing: KSeFSessionORM | None,
    ) -> PurchaseAuthContext:
        auth_token = settings.ksef_auth_token
        if not auth_token:
            raise AppError("KSEF_AUTH_TOKEN nie jest skonfigurowany.")

        try:
            tokens = self.auth_provider.get_tokens(nip, auth_token)
        except KSeFAuthError as exc:
            raise ExternalServiceError(f"Błąd uwierzytelnienia KSeF: {exc}") from exc

        now = datetime.now(UTC)
        if existing is not None and is_online_session(existing):
            existing.token_metadata_json = build_token_metadata(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                refresh_valid_until=tokens.refresh_valid_until,
                existing=existing.token_metadata_json,
            )
            existing.expires_at = tokens.access_valid_until
            existing.updated_at = now
            self.session.flush()
            self._journal(
                operation_type=KSeFOperationType.SESSION_RENEWED,
                severity=KSeFSeverity.SUCCESS,
                status="renewed",
                nip=nip,
                correlation_id=existing.id,
                message="Purchase auth renewed (online session preserved).",
            )
            return self._to_context(existing)

        if existing is not None:
            existing.token_metadata_json = build_token_metadata(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                refresh_valid_until=tokens.refresh_valid_until,
            )
            existing.session_reference = None
            existing.status = SESSION_AUTH_ACTIVE
            existing.expires_at = tokens.access_valid_until
            existing.updated_at = now
            self.session.flush()
            orm = existing
        else:
            orm = KSeFSessionORM(
                id=uuid4(),
                nip=nip,
                environment=self.auth_provider.environment,
                auth_method="token",
                session_reference=None,
                token_metadata_json=build_token_metadata(
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    refresh_valid_until=tokens.refresh_valid_until,
                ),
                status=SESSION_AUTH_ACTIVE,
                expires_at=tokens.access_valid_until,
                created_at=now,
                updated_at=now,
            )
            self.session.add(orm)
            self.session.flush()

        self._audit_open(actor_user_id, orm, event="ksef_purchase_auth.created")
        self._journal(
            operation_type=KSeFOperationType.SESSION_RENEWED,
            severity=KSeFSeverity.SUCCESS,
            status="authenticated",
            nip=nip,
            correlation_id=orm.id,
            message="Purchase auth established without online session.",
        )
        return self._to_context(orm)

    def _refresh_tokens(
        self,
        record: KSeFSessionORM,
        *,
        actor_user_id: UUID | None,
    ) -> PurchaseAuthContext:
        metadata = record.token_metadata_json or {}
        refresh_token = metadata.get("refresh_token")
        if not refresh_token:
            raise KSeFAuthError("Brak refresh token w rekordzie sesji.")

        tokens = self.auth_provider.refresh_access_token(refresh_token)
        record.token_metadata_json = build_token_metadata(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            refresh_valid_until=tokens.refresh_valid_until,
            existing=record.token_metadata_json,
        )
        record.expires_at = tokens.access_valid_until
        record.updated_at = datetime.now(UTC)
        self.session.flush()

        self._journal(
            operation_type=KSeFOperationType.SESSION_REFRESH,
            severity=KSeFSeverity.SUCCESS,
            status="refreshed",
            nip=record.nip,
            correlation_id=record.id,
            message="Purchase access token refreshed.",
        )
        return self._to_context(record)

    def _find_purchase_auth_record(self, nip: str) -> KSeFSessionORM | None:
        for status in _PURCHASE_AUTH_STATUSES:
            stmt = (
                select(KSeFSessionORM)
                .where(
                    KSeFSessionORM.nip == nip,
                    KSeFSessionORM.status == status,
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
                KSeFSessionORM.nip == nip,
                KSeFSessionORM.status.in_(_PURCHASE_AUTH_STATUSES),
            )
            .order_by(KSeFSessionORM.created_at.desc())
            .limit(1)
        )
        return self.session.execute(fallback).scalar_one_or_none()

    @staticmethod
    def _to_context(orm: KSeFSessionORM) -> PurchaseAuthContext:
        metadata = orm.token_metadata_json or {}
        access = metadata.get(KEY_ACCESS_TOKEN)
        if not access:
            raise AppError(f"Brak access token w rekordzie KSeF dla NIP {orm.nip}.")
        return PurchaseAuthContext(
            nip=orm.nip,
            access_token=access,
            expires_at=as_utc_aware(orm.expires_at),
            record_id=orm.id,
            auth_method=orm.auth_method or "token",
        )

    def _audit_open(self, actor_user_id: UUID | None, orm: KSeFSessionORM, *, event: str) -> None:
        if self.audit_service is None:
            return
        self.audit_service.record(
            actor_user_id=actor_user_id,
            actor_role="system",
            event_type=event,
            entity_type="ksef_session",
            entity_id=str(orm.id),
            after={"status": orm.status, "nip": orm.nip, "online": is_online_session(orm)},
        )

    def _journal(
        self,
        *,
        operation_type: KSeFOperationType,
        severity: KSeFSeverity,
        status: str,
        nip: str,
        correlation_id: UUID,
        message: str,
    ) -> None:
        if self._journal_service is None:
            return
        self._journal_service.log_event(
            operation_type=operation_type,
            severity=severity,
            status=status,
            short_description=message,
            correlation_id=correlation_id,
            metadata_json={"nip": nip, "source": "purchase_auth"},
        )
