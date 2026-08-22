"""Testy PurchaseAuthService — purchase auth bez sesji online."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AppError, ExternalServiceError
from app.domain.enums import KSeFOperationType, KSeFSeverity
from app.integrations.ksef.auth import KSeFAuthError, KSeFSession
from app.services.ksef_purchase_auth_service import PurchaseAuthService
from app.services.ksef_token_store import (
    SESSION_AUTH_ACTIVE,
    build_token_metadata,
)


@pytest.fixture()
def auth_provider() -> MagicMock:
    provider = MagicMock()
    provider.environment = "test"
    return provider


@pytest.fixture()
def service(mock_session: MagicMock, auth_provider: MagicMock) -> PurchaseAuthService:
    return PurchaseAuthService(
        session=mock_session,
        auth_provider=auth_provider,
        audit_service=MagicMock(),
        journal_service=MagicMock(),
    )


def _auth_orm(
    *,
    nip: str = "9670402857",
    access: str = "access-tok",
    refresh: str = "refresh-tok",
    expires_at: datetime | None = None,
    status: str = SESSION_AUTH_ACTIVE,
):
    orm = MagicMock()
    orm.id = uuid.uuid4()
    orm.nip = nip
    orm.status = status
    orm.auth_method = "token"
    orm.session_reference = None
    orm.expires_at = expires_at or (datetime.now(UTC) + timedelta(hours=1))
    orm.token_metadata_json = build_token_metadata(
        access_token=access,
        refresh_token=refresh,
        refresh_valid_until=datetime.now(UTC) + timedelta(days=7),
    )
    return orm


def _mock_no_record(mock_session: MagicMock) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result


def _mock_record(mock_session: MagicMock, orm) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = orm
    mock_session.execute.return_value = result


class TestEnsurePurchaseAuthNoToken:
    @patch("app.services.ksef_purchase_auth_service.settings")
    def test_full_auth_when_no_record(
        self,
        mock_settings,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        mock_settings.ksef_auth_token = "env-token"
        _mock_no_record(mock_session)
        auth_provider.get_tokens.return_value = KSeFSession(
            access_token="new-access",
            refresh_token="new-refresh",
            access_valid_until=datetime.now(UTC) + timedelta(hours=2),
            refresh_valid_until=datetime.now(UTC) + timedelta(days=1),
        )

        ctx = service.ensure_purchase_auth("9670402857")

        assert ctx.access_token == "new-access"
        auth_provider.get_tokens.assert_called_once()
        mock_session.add.assert_called_once()

    @patch("app.services.ksef_purchase_auth_service.settings")
    def test_scheduler_path_no_token_then_sync_ok(
        self,
        mock_settings,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        """Scheduler: brak tokena → ensure auth → OK."""
        mock_settings.ksef_auth_token = "env-token"
        _mock_no_record(mock_session)
        auth_provider.get_tokens.return_value = KSeFSession(
            access_token="sched-access",
            refresh_token="sched-refresh",
            access_valid_until=datetime.now(UTC) + timedelta(hours=1),
            refresh_valid_until=None,
        )

        ctx = service.ensure_purchase_auth("9670402857")
        assert ctx.access_token == "sched-access"


class TestEnsurePurchaseAuthRefresh:
    def test_expired_access_refreshes(
        self,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        orm = _auth_orm(
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        _mock_record(mock_session, orm)
        auth_provider.refresh_access_token.return_value = KSeFSession(
            access_token="refreshed-access",
            refresh_token="refresh-tok",
            access_valid_until=datetime.now(UTC) + timedelta(hours=1),
            refresh_valid_until=None,
        )

        ctx = service.ensure_purchase_auth("9670402857")

        assert ctx.access_token == "refreshed-access"
        auth_provider.refresh_access_token.assert_called_once_with("refresh-tok")
        auth_provider.get_tokens.assert_not_called()

    @patch("app.services.ksef_purchase_auth_service.settings")
    def test_refresh_failed_falls_back_to_full_auth(
        self,
        mock_settings,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        mock_settings.ksef_auth_token = "env-token"
        orm = _auth_orm(expires_at=datetime.now(UTC) - timedelta(hours=1))
        _mock_record(mock_session, orm)
        auth_provider.refresh_access_token.side_effect = KSeFAuthError("refresh denied")
        auth_provider.get_tokens.return_value = KSeFSession(
            access_token="full-auth-access",
            refresh_token="full-auth-refresh",
            access_valid_until=datetime.now(UTC) + timedelta(hours=1),
            refresh_valid_until=None,
        )

        ctx = service.ensure_purchase_auth("9670402857")

        assert ctx.access_token == "full-auth-access"
        auth_provider.get_tokens.assert_called_once()


class TestEnsurePurchaseAuthValidToken:
    def test_returns_existing_valid_token(
        self,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        orm = _auth_orm(access="still-valid")
        _mock_record(mock_session, orm)

        ctx = service.ensure_purchase_auth("9670402857")

        assert ctx.access_token == "still-valid"
        auth_provider.refresh_access_token.assert_not_called()
        auth_provider.get_tokens.assert_not_called()


class TestEnsurePurchaseAuthErrors:
    @patch("app.services.ksef_purchase_auth_service.settings")
    def test_missing_env_token_raises(
        self,
        mock_settings,
        service: PurchaseAuthService,
        mock_session: MagicMock,
    ):
        mock_settings.ksef_auth_token = None
        _mock_no_record(mock_session)

        with pytest.raises(AppError, match="KSEF_AUTH_TOKEN"):
            service.ensure_purchase_auth("9670402857")

    @patch("app.services.ksef_purchase_auth_service.settings")
    def test_auth_provider_error_wrapped(
        self,
        mock_settings,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        mock_settings.ksef_auth_token = "env-token"
        _mock_no_record(mock_session)
        auth_provider.get_tokens.side_effect = KSeFAuthError("KSeF down")

        with pytest.raises(ExternalServiceError, match="uwierzytelnienia"):
            service.ensure_purchase_auth("9670402857")

        op_types = [
            c.kwargs.get("operation_type")
            for c in service._journal_service.log_event.call_args_list
            if "operation_type" in c.kwargs
        ]
        assert KSeFOperationType.ERROR in op_types


class TestEnsurePurchaseAuthRedeemRetryJournal:
    @patch("app.services.ksef_purchase_auth_service.settings")
    def test_journals_retry_and_resume_on_transient_redeem(
        self,
        mock_settings,
        service: PurchaseAuthService,
        auth_provider: MagicMock,
        mock_session: MagicMock,
    ):
        """Callbacki redeem → Monitor RETRY (WARNING) + RESUME po sukcesie."""
        mock_settings.ksef_auth_token = "env-token"
        _mock_no_record(mock_session)
        corr = uuid.uuid4()

        def _get_tokens_with_callbacks(nip, token, **kwargs):
            on_retry = kwargs.get("on_transient_retry")
            on_recovered = kwargs.get("on_transient_recovered")
            if on_retry:
                on_retry(100, 1, 0.5, 0.0)
            if on_recovered:
                on_recovered(100, 1)
            return KSeFSession(
                access_token="new-access",
                refresh_token="new-refresh",
                access_valid_until=datetime.now(UTC) + timedelta(hours=1),
                refresh_valid_until=datetime.now(UTC) + timedelta(days=7),
            )

        auth_provider.get_tokens.side_effect = _get_tokens_with_callbacks

        ctx = service.ensure_purchase_auth("9670402857", correlation_id=corr)
        assert ctx.access_token == "new-access"

        ops = [
            (
                c.kwargs.get("operation_type"),
                c.kwargs.get("severity"),
                c.kwargs.get("correlation_id"),
            )
            for c in service._journal_service.log_event.call_args_list
        ]
        assert (KSeFOperationType.RETRY, KSeFSeverity.WARNING, corr) in ops
        assert (KSeFOperationType.RESUME, KSeFSeverity.SUCCESS, corr) in ops
