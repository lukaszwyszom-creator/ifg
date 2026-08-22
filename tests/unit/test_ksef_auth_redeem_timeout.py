"""Testy KSeF auth redeem timeout — status 100 / 450 (przejściowe) retry."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.integrations.ksef.auth import (
    KSeFAuthError,
    KSeFAuthProvider,
    _transient_auth_status_from_payload,
)


def _redeem_error_body(auth_status: int | None, *, exception_code: int = 21301) -> dict:
    if auth_status is None:
        details = ["Inny błąd bez statusu uwierzytelniania"]
    else:
        details = [
            f"Status uwierzytelniania ({auth_status}) nie pozwala na pobranie tokenów."
        ]
    return {
        "exception": {
            "exceptionDetailList": [
                {
                    "exceptionCode": exception_code,
                    "exceptionDescription": "Brak autoryzacji.",
                    "details": details,
                }
            ]
        }
    }


def _mock_400(auth_status: int | None, *, exception_code: int = 21301) -> MagicMock:
    body = _redeem_error_body(auth_status, exception_code=exception_code)
    response = MagicMock(status_code=400)
    response.json = MagicMock(return_value=body)
    response.text = str(body)[:300]
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request",
        request=MagicMock(),
        response=response,
    )
    return response


def _mock_200() -> MagicMock:
    response = MagicMock(status_code=200)
    response.json = MagicMock(
        return_value={
            "accessToken": {
                "token": "access-token-123",
                "validUntil": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            "refreshToken": {
                "token": "refresh-token-456",
                "validUntil": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            },
        }
    )
    return response


@pytest.fixture
def auth_provider() -> KSeFAuthProvider:
    """KSeFAuthProvider z domyślnym redeem timeout 120s."""
    return KSeFAuthProvider(
        environment="test",
        timeout_seconds=30,
        auth_redeem_timeout_seconds=120,
    )


@pytest.fixture
def auth_provider_short_timeout() -> KSeFAuthProvider:
    """KSeFAuthProvider z krótkim redeem timeout 2s (do testów timeout)."""
    return KSeFAuthProvider(
        environment="test",
        timeout_seconds=30,
        auth_redeem_timeout_seconds=2,
    )


class TestTransientAuthStatusParsing:
    def test_parses_status_100(self):
        status = _transient_auth_status_from_payload(_redeem_error_body(100))
        assert status == 100

    def test_parses_status_450(self):
        status = _transient_auth_status_from_payload(_redeem_error_body(450))
        assert status == 450

    def test_ignores_other_21301_without_known_transient_status(self):
        status = _transient_auth_status_from_payload(_redeem_error_body(200))
        assert status is None

    def test_ignores_non_21301(self):
        status = _transient_auth_status_from_payload(
            _redeem_error_body(100, exception_code=99999)
        )
        assert status is None


class TestRedeemTokensRetryStatus100:
    """Status 100 (auth not ready) — bounded retry."""

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_status_100_then_success(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Status 100 x2, potem sukces 200 — sync może kontynuować w tym samym jobie."""
        callbacks: list[tuple] = []
        recovered: list[tuple] = []

        mock_post.side_effect = [_mock_400(100), _mock_400(100), _mock_200()]

        result = auth_provider._redeem_tokens(
            "auth-token-dummy",
            on_transient_retry=lambda *args: callbacks.append(args),
            on_transient_recovered=lambda *args: recovered.append(args),
        )

        assert result.access_token == "access-token-123"
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
        assert len(callbacks) == 2
        assert callbacks[0][0] == 100
        assert recovered == [(100, 2)]

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_status_100_repeated_bounded_fail(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider_short_timeout: KSeFAuthProvider,
    ):
        """Status 100 przez cały limit → ERROR po wyczerpaniu (bez busy loop)."""
        mock_post.return_value = _mock_400(100)

        with pytest.raises(KSeFAuthError, match="token redeem error"):
            auth_provider_short_timeout._redeem_tokens("token-auth")

        assert mock_post.call_count > 1
        assert mock_sleep.call_count >= 1


class TestRedeemTokensRetryStatus450:
    """Test: kod retryuje status 450 (SENT — w toku) i finalnie zwraca tokeny."""

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_retries_status_450_then_success(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Status 450 x3 razy, potem sukces 200."""
        mock_post.side_effect = [_mock_400(450), _mock_400(450), _mock_400(450), _mock_200()]

        result = auth_provider._redeem_tokens("auth-token-dummy")

        assert result.access_token == "access-token-123"
        assert result.refresh_token == "refresh-token-456"
        assert isinstance(result.access_valid_until, datetime)
        assert isinstance(result.refresh_valid_until, datetime)
        assert mock_post.call_count == 4
        assert mock_sleep.call_count == 3

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_retries_with_exponential_backoff(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Retry z eksponencjalnym opóźnieniem (0.5, 0.75, ...)."""
        mock_post.side_effect = [_mock_400(450), _mock_400(450), _mock_200()]

        auth_provider._redeem_tokens("token-auth")

        calls = mock_sleep.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == 0.5
        assert calls[1][0][0] == 0.75

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_permanent_400_raises_immediately(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Trwały 400 (nie 100/450) → fail natychmiast, bez nieskończonego retry."""
        mock_post.return_value = _mock_400(None, exception_code=99999)

        with pytest.raises(KSeFAuthError, match="token redeem error"):
            auth_provider._redeem_tokens("token")

        assert mock_post.call_count == 1

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_21301_without_transient_status_raises_immediately(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """21301 bez statusu 100/450 nie wchodzi w retry."""
        mock_post.return_value = _mock_400(None, exception_code=21301)

        with pytest.raises(KSeFAuthError, match="token redeem error"):
            auth_provider._redeem_tokens("token")

        assert mock_post.call_count == 1


class TestRedeemTokensSuccessNoRetry:
    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_normal_success_without_retry(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        mock_post.return_value = _mock_200()
        recovered: list = []

        result = auth_provider._redeem_tokens(
            "token",
            on_transient_recovered=lambda *a: recovered.append(a),
        )

        assert result.access_token == "access-token-123"
        assert mock_post.call_count == 1
        assert mock_sleep.call_count == 0
        assert recovered == []


class TestRedeemTokensTimeout:
    """Status przejściowy utrzymuje się ponad limit timeout → ERROR."""

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_status_450_timeout_exceeded(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider_short_timeout: KSeFAuthProvider,
    ):
        mock_post.return_value = _mock_400(450)

        with pytest.raises(KSeFAuthError, match="token redeem error"):
            auth_provider_short_timeout._redeem_tokens("token-auth")

        assert mock_post.call_count > 0

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_connection_error_raises(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        mock_post.side_effect = httpx.ConnectError("Network error")

        with pytest.raises(KSeFAuthError, match="KSeF connection error"):
            auth_provider._redeem_tokens("token-secret")


class TestRedeemTokensConfigurableTimeout:
    """Test: timeout redeem można konfigurować."""

    def test_provider_accepts_custom_redeem_timeout(self):
        provider1 = KSeFAuthProvider(
            environment="test",
            timeout_seconds=30,
            auth_redeem_timeout_seconds=60,
        )
        assert provider1._auth_redeem_timeout == 60

        provider2 = KSeFAuthProvider(
            environment="test",
            timeout_seconds=30,
            auth_redeem_timeout_seconds=300,
        )
        assert provider2._auth_redeem_timeout == 300

        provider3 = KSeFAuthProvider(
            environment="test",
            timeout_seconds=30,
        )
        assert provider3._auth_redeem_timeout == 120

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_longer_timeout_allows_more_retries(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
    ):
        provider_long = KSeFAuthProvider(
            environment="test",
            timeout_seconds=30,
            auth_redeem_timeout_seconds=10,
        )
        mock_post.return_value = _mock_400(450)

        with pytest.raises(KSeFAuthError):
            provider_long._redeem_tokens("token")

        assert mock_post.call_count > 1


class TestRedeemTokensErrorHandling:
    """Test: obsługa błędów bez ujawniania tokenów."""

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_error_message_does_not_contain_token(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        mock_post.side_effect = httpx.ConnectError("Test error")

        try:
            auth_provider._redeem_tokens("secret-token-12345")
        except KSeFAuthError as e:
            error_msg = str(e)
            assert "secret-token-12345" not in error_msg
            assert "connection error" in error_msg.lower()

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_malformed_json_in_transient_response(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        mock_post.return_value = MagicMock(
            status_code=400,
            json=MagicMock(side_effect=ValueError("Invalid JSON")),
            text="bad",
        )
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400",
            request=MagicMock(),
            response=mock_post.return_value,
        )

        with pytest.raises(KSeFAuthError):
            auth_provider._redeem_tokens("token")
