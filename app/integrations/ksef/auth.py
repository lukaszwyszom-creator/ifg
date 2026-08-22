"""KSeF 2.0 — uwierzytelnienie tokenem KSeF z szyfrowaniem RSA-OAEP.

Przepływ uwierzytelnienia:
  1. POST /auth/challenge          → {challenge, timestampMs, ...}
  2. Szyfrowanie tokena:           KSEF_TOKEN|timestampMs → RSA-OAEP(SHA-256)
  3. POST /auth/ksef-token         → {referenceNumber, authenticationToken}
  4. POST /auth/token/redeem       → {accessToken, refreshToken}
  5. POST /sessions/online         → w KSeFClient (wymagany accessToken)
"""

from __future__ import annotations

import base64
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate

logger = logging.getLogger(__name__)

_KSEF_URLS = {
    "test": "https://api-test.ksef.mf.gov.pl/v2",
    "production": "https://api.ksef.mf.gov.pl/v2",
}

_USAGE_TOKEN_ENCRYPTION = "KsefTokenEncryption"

# Statusy auth uznawane za przejściowe przy redeem (nie failujemy od razu).
# 100 — uwierzytelnianie jeszcze niegotowe (incydent 21.08.2026)
# 450 — SENT / w toku (dotychczasowa obsługa)
_TRANSIENT_AUTH_STATUSES = frozenset({100, 450})
_AUTH_STATUS_IN_DETAILS_RE = re.compile(
    r"(?i)status\s+uwierzytelniania\s*\((\d+)\)"
)

TransientRetryCallback = Callable[[int, int, float, float], None]
TransientRecoveredCallback = Callable[[int, int], None]


class KSeFAuthError(Exception):
    """Błąd uwierzytelnienia w KSeF."""


@dataclass
class KSeFSession:
    """Tokeny dostępowe zwrócone po pomyślnym uwierzytelnieniu."""

    access_token: str
    refresh_token: str
    access_valid_until: datetime | None
    refresh_valid_until: datetime | None


class KSeFAuthProvider:
    def __init__(
        self,
        environment: str,
        timeout_seconds: int = 30,
        auth_redeem_timeout_seconds: int = 120,
    ) -> None:
        self.environment = environment
        self._base_url = _KSEF_URLS.get(environment, _KSEF_URLS["test"])
        self._timeout = timeout_seconds
        self._auth_redeem_timeout = auth_redeem_timeout_seconds

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def get_tokens(
        self,
        nip: str,
        ksef_auth_token: str,
        *,
        on_transient_retry: TransientRetryCallback | None = None,
        on_transient_recovered: TransientRecoveredCallback | None = None,
    ) -> KSeFSession:
        """Pełny przepływ uwierzytelnienia — zwraca parę access/refresh tokenów."""
        challenge_data = self._get_challenge()
        encrypted = self._encrypt_token(ksef_auth_token, challenge_data["timestampMs"])
        auth_init = self._init_token_auth(nip, challenge_data["challenge"], encrypted)
        return self._redeem_tokens(
            auth_init["authenticationToken"]["token"],
            on_transient_retry=on_transient_retry,
            on_transient_recovered=on_transient_recovered,
        )

    def refresh_access_token(self, refresh_token: str) -> KSeFSession:
        """Odświeżenie access tokena przy użyciu refresh tokena."""
        url = f"{self._base_url}/auth/token/refresh"
        try:
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {refresh_token}"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise KSeFAuthError(
                f"KSeF token refresh error ({exc.response.status_code}): "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise KSeFAuthError(f"KSeF connection error: {exc}") from exc

        return KSeFSession(
            access_token=data["accessToken"]["token"],
            refresh_token=refresh_token,
            access_valid_until=_parse_dt(data["accessToken"].get("validUntil")),
            refresh_valid_until=None,
        )

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _get_challenge(self) -> dict:
        """POST /auth/challenge — brak ciała żądania."""
        url = f"{self._base_url}/auth/challenge"
        try:
            resp = httpx.post(url, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise KSeFAuthError(
                f"KSeF challenge error ({exc.response.status_code}): "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise KSeFAuthError(f"KSeF connection error: {exc}") from exc

    def _fetch_token_encryption_key(self) -> bytes:
        """Pobiera klucz publiczny MF do szyfrowania tokena (DER)."""
        url = f"{self._base_url}/security/public-key-certificates"
        try:
            resp = httpx.get(url, timeout=self._timeout)
            resp.raise_for_status()
            certs = resp.json()
        except httpx.HTTPStatusError as exc:
            raise KSeFAuthError(
                f"KSeF public key fetch error ({exc.response.status_code}): "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise KSeFAuthError(f"KSeF connection error: {exc}") from exc

        for cert_info in certs:
            if _USAGE_TOKEN_ENCRYPTION in cert_info.get("usage", []):
                return base64.b64decode(cert_info["certificate"])

        raise KSeFAuthError(
            f"Nie znaleziono certyfikatu KSeF o użyciu '{_USAGE_TOKEN_ENCRYPTION}'."
        )

    def _encrypt_token(self, ksef_token: str, timestamp_ms: int) -> str:
        """Szyfruje token RSA-OAEP (SHA-256) i koduje w Base64."""
        cert_der = self._fetch_token_encryption_key()
        cert = load_der_x509_certificate(cert_der)
        public_key = cert.public_key()

        plaintext = f"{ksef_token}|{timestamp_ms}".encode("utf-8")
        encrypted = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode("ascii")

    def _init_token_auth(
        self, nip: str, challenge: str, encrypted_token: str
    ) -> dict:
        """POST /auth/ksef-token — inicjuje uwierzytelnienie tokenem."""
        url = f"{self._base_url}/auth/ksef-token"
        payload = {
            "challenge": challenge,
            "contextIdentifier": {"type": "Nip", "value": nip},
            "encryptedToken": encrypted_token,
        }
        try:
            resp = httpx.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise KSeFAuthError(
                f"KSeF init token error ({exc.response.status_code}): "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise KSeFAuthError(f"KSeF connection error: {exc}") from exc

    def _redeem_tokens(
        self,
        authentication_token: str,
        *,
        on_transient_retry: TransientRetryCallback | None = None,
        on_transient_recovered: TransientRecoveredCallback | None = None,
    ) -> KSeFSession:
        """POST /auth/token/redeem — wymienia authenticationToken na access/refresh.

        KSeF 2.0 przetwarza uwierzytelnienie asynchronicznie. Przy HTTP 400 +
        exceptionCode 21301 i statusie przejściowym (100 lub 450) ponawiamy
        redeem z wykładniczym backoffiem aż do limitu czasu
        (domyślnie ``auth_redeem_timeout_seconds`` = 120 s).
        Inne 21301 / 400 kończą się natychmiastowym błędem.
        """
        url = f"{self._base_url}/auth/token/redeem"
        max_wait_seconds = float(self._auth_redeem_timeout)
        delay = 0.5
        elapsed = 0.0
        attempt = 0
        last_transient_status: int | None = None

        while True:
            try:
                resp = httpx.post(
                    url,
                    headers={"Authorization": f"Bearer {authentication_token}"},
                    timeout=self._timeout,
                )
            except httpx.RequestError as exc:
                raise KSeFAuthError(f"KSeF connection error: {exc}") from exc

            transient_status = _transient_auth_status_from_http_response(resp)
            if (
                transient_status is not None
                and elapsed < max_wait_seconds
            ):
                attempt += 1
                last_transient_status = transient_status
                logger.info(
                    "KSeF auth w toku (status %s), ponowna próba za %.1fs "
                    "(attempt=%s elapsed=%.1fs max_wait=%.1fs)",
                    transient_status,
                    delay,
                    attempt,
                    elapsed,
                    max_wait_seconds,
                )
                if on_transient_retry is not None:
                    on_transient_retry(transient_status, attempt, delay, elapsed)
                time.sleep(delay)
                elapsed += delay
                delay = min(delay * 1.5, 5.0)
                continue

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise KSeFAuthError(
                    f"KSeF token redeem error ({exc.response.status_code}): "
                    f"{exc.response.text[:300]}"
                ) from exc

            data = resp.json()
            if (
                attempt > 0
                and last_transient_status is not None
                and on_transient_recovered is not None
            ):
                on_transient_recovered(last_transient_status, attempt)
            return KSeFSession(
                access_token=data["accessToken"]["token"],
                refresh_token=data["refreshToken"]["token"],
                access_valid_until=_parse_dt(data["accessToken"].get("validUntil")),
                refresh_valid_until=_parse_dt(data["refreshToken"].get("validUntil")),
            )


def _auth_status_from_exception_details(details: list | tuple) -> int | None:
    """Wyciąga numer statusu uwierzytelniania z pola details wyjątku KSeF."""
    for item in details:
        text = str(item)
        match = _AUTH_STATUS_IN_DETAILS_RE.search(text)
        if match:
            return int(match.group(1))
    return None


def _transient_auth_status_from_payload(payload: dict) -> int | None:
    """Zwraca status przejściowy (100/450) z ciała błędu redeem, inaczej None.

    Nie retry'ujemy każdego 21301 — tylko gdy da się odczytać status
    uwierzytelniania należący do ``_TRANSIENT_AUTH_STATUSES``.
    """
    detail_list = (
        payload.get("exception", {}).get("exceptionDetailList", [])
        if isinstance(payload, dict)
        else []
    )
    for detail in detail_list:
        if not isinstance(detail, dict):
            continue
        if detail.get("exceptionCode") != 21301:
            continue
        status = _auth_status_from_exception_details(detail.get("details") or [])
        if status in _TRANSIENT_AUTH_STATUSES:
            return status
    return None


def _transient_auth_status_from_http_response(resp: httpx.Response) -> int | None:
    if resp.status_code != 400:
        return None
    try:
        payload = resp.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _transient_auth_status_from_payload(payload)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
