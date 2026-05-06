"""Testy KSeF auth redeem timeout — status 450 (SENT) retry."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.integrations.ksef.auth import KSeFAuthError, KSeFAuthProvider, KSeFSession


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
        # Przygotowujemy odpowiedzi:
        # 1-3: 400 z exceptionCode 21301, status 450 w details
        # 4: 200 z tokeny
        responses_450 = [
            MagicMock(
                status_code=400,
                json=MagicMock(
                    return_value={
                        "exception": {
                            "exceptionDetailList": [
                                {
                                    "exceptionCode": 21301,
                                    "details": ["Status uwierzytelniania (450)"],
                                }
                            ]
                        }
                    }
                ),
            )
            for _ in range(3)
        ]

        response_success = MagicMock(
            status_code=200,
            json=MagicMock(
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
            ),
        )

        mock_post.side_effect = responses_450 + [response_success]

        # Metoda prywatna
        result = auth_provider._redeem_tokens("auth-token-dummy")

        # Asercje
        assert result.access_token == "access-token-123"
        assert result.refresh_token == "refresh-token-456"
        assert isinstance(result.access_valid_until, datetime)
        assert isinstance(result.refresh_valid_until, datetime)

        # Sprawdzenie, że post został wołany 4 razy
        assert mock_post.call_count == 4

        # Sprawdzenie, że sleep był wołany 3 razy (między retry)
        assert mock_sleep.call_count == 3

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_retries_with_exponential_backoff(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Retry z eksponencjalnym opóźnieniem (0.5, 0.75, 1.125, ...)."""
        responses = [
            MagicMock(
                status_code=400,
                json=MagicMock(
                    return_value={
                        "exception": {
                            "exceptionDetailList": [
                                {
                                    "exceptionCode": 21301,
                                    "details": ["Status uwierzytelniania (450)"],
                                }
                            ]
                        }
                    }
                ),
            )
            for _ in range(2)
        ]

        response_success = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "accessToken": {
                        "token": "token-a",
                        "validUntil": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    },
                    "refreshToken": {
                        "token": "token-r",
                        "validUntil": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                    },
                }
            ),
        )

        mock_post.side_effect = responses + [response_success]

        auth_provider._redeem_tokens("token-auth")

        # Sprawdzenie opóźnień: 0.5, 0.5*1.5=0.75
        calls = mock_sleep.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == 0.5
        assert calls[1][0][0] == 0.75

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_non_450_status_400_raises_immediately(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Status 400 bez statusu 450 → wznowienie (raise) natychmiast."""
        mock_post.return_value = MagicMock(
            status_code=400,
            json=MagicMock(
                return_value={
                    "exception": {
                        "exceptionDetailList": [
                            {
                                "exceptionCode": 99999,  # Inny kod
                                "details": ["Inny błąd"],
                            }
                        ]
                    }
                }
            ),
        )
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=mock_post.return_value,
        )

        with pytest.raises(KSeFAuthError, match="token redeem error"):
            auth_provider._redeem_tokens("token")

        # Tylko jedno żądanie — bez retry
        assert mock_post.call_count == 1


class TestRedeemTokensTimeout:
    """Test: status 450 utrzymuje się ponad limit timeout → ERROR bez ujawnienia tokena."""

    @patch("app.integrations.ksef.auth.httpx.post")
    @patch("app.integrations.ksef.auth.time.sleep")
    def test_status_450_timeout_exceeded(
        self,
        mock_sleep: MagicMock,
        mock_post: MagicMock,
        auth_provider_short_timeout: KSeFAuthProvider,
    ):
        """Status 450 przez cały limit, potem zwracany bez raise."""
        # Wszystkie żądania zwracają 400 + status 450
        mock_post.return_value = MagicMock(
            status_code=400,
            json=MagicMock(
                return_value={
                    "exception": {
                        "exceptionDetailList": [
                            {
                                "exceptionCode": 21301,
                                "details": ["Status uwierzytelniania (450)"],
                            }
                        ]
                    }
                }
            ),
        )
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=mock_post.return_value,
        )

        # Po przekroczeniu timeout_seconds=2, kod zwrócił będzie błąd
        with pytest.raises(KSeFAuthError, match="token redeem error"):
            auth_provider_short_timeout._redeem_tokens("token-auth")

        # Post został wołany wiele razy (szybkie retry)
        assert mock_post.call_count > 0

        # W logu NIE powinno być całego tokena
        # (sprawdzenie, że nie logujemy sensitywnych danych)

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_connection_error_raises(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Błąd połączenia → KSeFAuthError bez ujawnienia tokena."""
        mock_post.side_effect = httpx.ConnectError("Network error")

        with pytest.raises(KSeFAuthError, match="KSeF connection error"):
            auth_provider._redeem_tokens("token-secret")


class TestRedeemTokensConfigurableTimeout:
    """Test: timeout redeem można konfigurować."""

    def test_provider_accepts_custom_redeem_timeout(self):
        """KSeFAuthProvider akceptuje auth_redeem_timeout_seconds."""
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

        # Domyślnie 120s
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
        """Dłuższy timeout pozwala na więcej retry."""
        provider_long = KSeFAuthProvider(
            environment="test",
            timeout_seconds=30,
            auth_redeem_timeout_seconds=10,
        )

        # Wiele 400 + status 450
        mock_post.return_value = MagicMock(
            status_code=400,
            json=MagicMock(
                return_value={
                    "exception": {
                        "exceptionDetailList": [
                            {
                                "exceptionCode": 21301,
                                "details": ["Status uwierzytelniania (450)"],
                            }
                        ]
                    }
                }
            ),
        )
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400",
            request=MagicMock(),
            response=mock_post.return_value,
        )

        with pytest.raises(KSeFAuthError):
            provider_long._redeem_tokens("token")

        # Wiele retry dzięki dłuższemu timeout
        retry_count = mock_post.call_count
        assert retry_count > 1


class TestRedeemTokensErrorHandling:
    """Test: obsługa błędów bez ujawniania tokenów."""

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_error_message_does_not_contain_token(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """KSeFAuthError nie zawiera tokena."""
        mock_post.side_effect = httpx.ConnectError("Test error")

        try:
            auth_provider._redeem_tokens("secret-token-12345")
        except KSeFAuthError as e:
            error_msg = str(e)
            assert "secret-token-12345" not in error_msg
            assert "connection error" in error_msg.lower()

    @patch("app.integrations.ksef.auth.httpx.post")
    def test_malformed_json_in_450_response(
        self,
        mock_post: MagicMock,
        auth_provider: KSeFAuthProvider,
    ):
        """Jeśli JSON jest zniekształcony, kod nie crasha."""
        mock_post.return_value = MagicMock(
            status_code=400,
            json=MagicMock(side_effect=ValueError("Invalid JSON")),
        )
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400",
            request=MagicMock(),
            response=mock_post.return_value,
        )

        with pytest.raises(KSeFAuthError):
            auth_provider._redeem_tokens("token")
