"""KSeF 2.0 — klient HTTP do operacji na sesjach i fakturach.

Wymaga Bearer accessToken uzyskanego przez KSeFAuthProvider.get_tokens().
Faktury są szyfrowane AES-256-CBC; klucz symetryczny jest generowany przy
otwarciu sesji i przechowywany w token_metadata_json.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import random
import time
from dataclasses import dataclass, field

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.x509 import load_der_x509_certificate

logger = logging.getLogger(__name__)

# Statusy HTTP traktowane jako przejściowe (warte retry)
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Przyjmowane sukcesowe kody HTTP (202 dla invoice send/session open, 204 dla close)
_SUCCESS_STATUS_CODES = frozenset({200, 201, 202, 204})

_USAGE_SYMMETRIC_KEY = "SymmetricKeyEncryption"


class KSeFClientError(Exception):
    """Błąd komunikacji z KSeF."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.transient = transient


class KSeFSessionExpiredError(KSeFClientError):
    """KSeF zwrócił 401/403 — access token wygasł lub jest nieważny."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message, status_code=status_code, transient=False)


@dataclass
class KSeFOnlineSession:
    """Dane otwartej sesji interaktywnej z kluczem symetrycznym."""

    session_reference: str
    symmetric_key: bytes           # 32 bajty — AES-256
    initialization_vector: bytes   # 16 bajtów — AES-256-CBC IV
    valid_until: str | None        # ISO 8601


@dataclass
class SendInvoiceResult:
    reference_number: str
    processing_code: int = 202
    processing_description: str = "Accepted"


@dataclass
class InvoiceStatusResult:
    processing_code: int           # 200 = przyjęta, 100 = przetwarzanie, 400 = odrzucona
    processing_description: str
    ksef_reference_number: str | None
    upo: bytes | None = None
    upo_url: str | None = None


@dataclass
class ReceivedInvoiceResult:
    """Faktura odebrana z KSeF — numer referencyjny i zdekryptowany XML FA(3)."""

    ksef_reference_number: str
    xml_bytes: bytes


@dataclass
class RetryConfig:
    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0


_KSEF_URLS = {
    "test": "https://api-test.ksef.mf.gov.pl/v2",
    "production": "https://api.ksef.mf.gov.pl/v2",
}

# FA(3) — kod formularza wymagany przy otwieraniu sesji interaktywnej
_FORM_CODE = {
    "systemCode": "FA (3)",
    "schemaVersion": "1-0E",
    "value": "FA",
}

# Metadata query — zakupy (Subject2) w prod KSeF v2
_METADATA_SUBJECT_PURCHASE = "Subject2"
_METADATA_DATE_TYPES = ("PermanentStorage", "Invoicing")
_METADATA_PAGE_SIZE = 50
_REQUEST_MIN_INTERVAL = 1.2


def _format_metadata_datetime(date_str: str, *, end_of_day: bool = False) -> str:
    from datetime import date as date_cls, datetime, time, timezone

    parsed = date_cls.fromisoformat(date_str)
    if end_of_day:
        dt = datetime.combine(parsed, time(23, 59, 59), tzinfo=timezone.utc)
    else:
        dt = datetime.combine(parsed, time(0, 0, 0), tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_metadata_invoice_refs(payload: dict) -> list[str]:
    candidates: list[dict] = []
    for key in ("invoices", "invoiceList", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates = [item for item in value if isinstance(item, dict)]
            break

    refs: list[str] = []
    for item in candidates:
        ref = item.get("ksefNumber") or item.get("ksefReferenceNumber")
        if isinstance(ref, str) and ref:
            refs.append(ref)
    return refs


class KSeFClient:
    def __init__(
        self,
        environment: str,
        timeout_seconds: int,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._base_url = _KSEF_URLS.get(environment, _KSEF_URLS["test"])
        self._timeout = timeout_seconds
        self._retry = retry_config or RetryConfig()
        self._last_purchase_request_monotonic: float | None = None

    # -------------------------------------------------------------------------
    # SESSION MANAGEMENT
    # -------------------------------------------------------------------------

    def open_online_session(self, access_token: str) -> KSeFOnlineSession:
        """POST /sessions/online — otwiera sesję interaktywną FA(3).

        Generuje losowy klucz AES-256 i IV, szyfruje klucz kluczem publicznym MF
        (RSA-OAEP SHA-256), a następnie otwiera sesję interaktywną.
        """
        symmetric_key = os.urandom(32)
        iv = os.urandom(16)

        encrypted_symmetric_key = self._encrypt_symmetric_key(symmetric_key)

        resp = self._request_with_retry(
            method="POST",
            path="/sessions/online",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "formCode": _FORM_CODE,
                "encryption": {
                    "encryptedSymmetricKey": base64.b64encode(encrypted_symmetric_key).decode("ascii"),
                    "initializationVector": base64.b64encode(iv).decode("ascii"),
                },
            },
        )
        data = resp.json()
        return KSeFOnlineSession(
            session_reference=data["referenceNumber"],
            symmetric_key=symmetric_key,
            initialization_vector=iv,
            valid_until=data.get("validUntil"),
        )

    def close_online_session(self, access_token: str, session_reference: str) -> None:
        """POST /sessions/online/{referenceNumber}/close — zamknięcie sesji."""
        try:
            self._request_with_retry(
                method="POST",
                path=f"/sessions/online/{session_reference}/close",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except KSeFClientError as exc:
            logger.warning(
                "KSeF close session failed (%s): %s",
                exc.status_code,
                exc,
            )

    # -------------------------------------------------------------------------
    # INVOICE OPERATIONS
    # -------------------------------------------------------------------------

    def send_invoice(
        self,
        access_token: str,
        session_reference: str,
        symmetric_key: bytes,
        iv: bytes,
        invoice_xml: bytes,
    ) -> SendInvoiceResult:
        """POST /sessions/online/{ref}/invoices — wysyła zaszyfrowaną fakturę."""
        encrypted_invoice = _aes_cbc_encrypt(invoice_xml, symmetric_key, iv)

        invoice_hash = base64.b64encode(hashlib.sha256(invoice_xml).digest()).decode("ascii")
        enc_invoice_hash = base64.b64encode(hashlib.sha256(encrypted_invoice).digest()).decode("ascii")

        resp = self._request_with_retry(
            method="POST",
            path=f"/sessions/online/{session_reference}/invoices",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "invoiceHash": invoice_hash,
                "invoiceSize": len(invoice_xml),
                "encryptedInvoiceHash": enc_invoice_hash,
                "encryptedInvoiceSize": len(encrypted_invoice),
                "encryptedInvoiceContent": base64.b64encode(encrypted_invoice).decode("ascii"),
            },
        )
        data = resp.json()
        return SendInvoiceResult(reference_number=data["referenceNumber"])

    def get_invoice_status(
        self,
        access_token: str,
        session_reference: str,
        invoice_reference: str,
    ) -> InvoiceStatusResult:
        """GET /sessions/{ref}/invoices/{invoiceRef} — sprawdza status faktury.

        Mapowanie na kody przetwarzania:
          200 = KSeF przydzielił numer (ksefNumber != null)
          100 = przetwarzanie w toku
          400 = faktura odrzucona (obecna na liście failed)
        """
        resp = self._request_with_retry(
            method="GET",
            path=f"/sessions/{session_reference}/invoices/{invoice_reference}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = resp.json()
        ksef_number = data.get("ksefNumber")

        if ksef_number:
            return InvoiceStatusResult(
                processing_code=200,
                processing_description="Faktura przyjęta przez KSeF",
                ksef_reference_number=ksef_number,
                upo_url=data.get("upoDownloadUrl"),
            )

        # Sprawdź listę odrzuconych
        failed_invoice = self._get_failed_invoice_entry(
            access_token, session_reference, invoice_reference
        )
        if failed_invoice is not None:
            return InvoiceStatusResult(
                processing_code=400,
                processing_description=self._format_failed_invoice_message(failed_invoice),
                ksef_reference_number=None,
            )

        return InvoiceStatusResult(
            processing_code=100,
            processing_description="Faktura w kolejce przetwarzania",
            ksef_reference_number=None,
        )

    @staticmethod
    def _format_failed_invoice_message(failed_invoice: dict) -> str:
        status = failed_invoice.get("status")
        if not isinstance(status, dict):
            return "Faktura odrzucona przez KSeF"

        description = str(status.get("description") or "").strip()
        details = status.get("details") or []
        detail_parts: list[str] = []
        if isinstance(details, list):
            for item in details:
                text = str(item).strip()
                if text:
                    detail_parts.append(text)

        if description and detail_parts:
            if detail_parts[0] == description:
                return description
            return f"{description}: {'; '.join(detail_parts)}"
        if description:
            return description
        if detail_parts:
            return "; ".join(detail_parts)

        code = status.get("code")
        if code is not None:
            return f"Faktura odrzucona przez KSeF (kod {code})"
        return "Faktura odrzucona przez KSeF"

    def _get_failed_invoice_entry(
        self, access_token: str, session_reference: str, invoice_reference: str
    ) -> dict | None:
        """Zwraca wpis faktury z listy odrzuconych w sesji (z opisem błędu KSeF)."""
        try:
            resp = self._request_with_retry(
                method="GET",
                path=f"/sessions/{session_reference}/invoices/failed",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            data = resp.json()
            for inv in data.get("invoices", []):
                if inv.get("referenceNumber") == invoice_reference:
                    return inv
        except KSeFClientError:
            pass
        return None

    def _is_invoice_failed(
        self, access_token: str, session_reference: str, invoice_reference: str
    ) -> bool:
        """Sprawdza czy faktura jest na liście odrzuconych w sesji."""
        return self._get_failed_invoice_entry(
            access_token, session_reference, invoice_reference
        ) is not None

    def query_received_invoices(
        self,
        access_token: str,
        session_reference: str,
        symmetric_key: bytes,
        iv: bytes,
        invoicing_date_from: str,
        invoicing_date_to: str,
        subject_type: str = "subject2",
    ) -> list[ReceivedInvoiceResult]:
        """Pobiera faktury zakupowe (odebrane) z KSeF za podany zakres dat.

        Flow (subject2 / zakupy):
        1. POST /invoices/query/metadata (Subject2, PermanentStorage/Invoicing).
        2. Dla każdego ksefNumber: GET /invoices/ksef/{ref} → XML (application/xml).

        Fallback (subject1/subject3 lub brak metadata endpoint):
        1. GET endpointy sesyjne dla received invoices.
        2. POST query fallback + polling.
        3. GET /invoices/{ref} → decrypt AES-256-CBC
        """
        if subject_type == "subject2":
            metadata_refs = self._query_purchase_metadata_refs(
                access_token=access_token,
                date_from=invoicing_date_from,
                date_to=invoicing_date_to,
            )
            if metadata_refs is not None:
                logger.info(
                    "KSeF received invoices via metadata query: count=%d date_from=%s date_to=%s",
                    len(metadata_refs),
                    invoicing_date_from,
                    invoicing_date_to,
                )
                return self._download_metadata_purchase_invoices(
                    access_token=access_token,
                    invoice_refs=metadata_refs,
                )

        headers = {"Authorization": f"Bearer {access_token}"}

        def _extract_invoice_refs(payload: dict | list) -> list[str]:
            candidates: list[dict] = []
            if isinstance(payload, list):
                candidates = [item for item in payload if isinstance(item, dict)]
            elif isinstance(payload, dict):
                for key in ("invoiceList", "invoices", "items", "results"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        candidates = [item for item in value if isinstance(item, dict)]
                        break

            refs: list[str] = []
            for item in candidates:
                ref = item.get("ksefReferenceNumber") or item.get("ksefNumber")
                if isinstance(ref, str) and ref:
                    refs.append(ref)
            return refs

        # 1. Najpierw spróbuj GET endpointów, które w TE zgłaszają Allow: GET.
        get_candidates = [
            f"/sessions/{session_reference}/invoices/received",
            f"/sessions/{session_reference}/invoices/query",
            f"/sessions/{session_reference}/invoices",
        ]
        get_param_variants = [
            {
                "invoiceType": "received",
                "subjectType": subject_type,
                "invoicingDateFrom": invoicing_date_from,
                "invoicingDateTo": invoicing_date_to,
            },
            {
                "subjectType": subject_type,
                "invoicingDateFrom": invoicing_date_from,
                "invoicingDateTo": invoicing_date_to,
            },
            {
                "invoiceType": "received",
                "invoicingDateFrom": invoicing_date_from,
                "invoicingDateTo": invoicing_date_to,
            },
            {
                "invoicingDateFrom": invoicing_date_from,
                "invoicingDateTo": invoicing_date_to,
            },
        ]

        invoice_refs: list[str] = []
        query_ref: str | None = None
        poll_path_prefix: str | None = None
        last_exc: KSeFClientError | None = None
        empty_get_succeeded = False
        post_fallback_attempted = False
        post_fallback_only_skipable = False

        def _is_wrong_invoice_reference_error(exc: KSeFClientError) -> bool:
            return exc.status_code == 400 and "21405" in str(exc)

        get_done = False
        for candidate in get_candidates:
            if get_done:
                break
            for params in get_param_variants:
                # DIAGNOSTICS: log endpoint and params (no token values)
                logger.info(
                    "KSeF query_received_invoices GET attempt: endpoint=%s params=%s "
                    "invoiceReferenceNumber_present=%s",
                    candidate,
                    {k: v for k, v in params.items()},
                    "invoiceReferenceNumber" in params,
                )
                try:
                    resp = self._request_with_retry(
                        method="GET",
                        path=candidate,
                        headers=headers,
                        params=params,
                    )
                except KSeFClientError as exc:
                    if exc.status_code in (404, 405) or _is_wrong_invoice_reference_error(exc):
                        last_exc = exc
                        logger.warning(
                            "KSeF GET endpoint %s unavailable (%s), trying next fallback",
                            candidate,
                            exc.status_code,
                        )
                        break
                    raise

                data = resp.json()
                if isinstance(data, dict) and isinstance(data.get("referenceNumber"), str):
                    query_ref = data["referenceNumber"]
                    poll_path_prefix = candidate
                    logger.info("KSeF query received invoices: queryRef=%s", query_ref)
                    get_done = True
                    break

                invoice_refs = _extract_invoice_refs(data)
                if invoice_refs:
                    logger.info(
                        "KSeF received invoices via %s: count=%d",
                        candidate,
                        len(invoice_refs),
                    )
                    get_done = True
                    break

                # Sukces bez listy faktur traktujemy jako pusty wynik.
                logger.info("KSeF received invoices via %s: empty result", candidate)
                empty_get_succeeded = True

        # 2. Fallback do POST endpointów query.
        # UWAGA: NIE używamy /sessions/online/{ref}/invoices/query — KSeF v2
        # interpretuje ten path jako /sessions/online/{ref}/invoices/{invoiceReferenceNumber}
        # (gdzie invoiceReferenceNumber="query") i zwraca 400 / exceptionCode 21405.
        if not invoice_refs and query_ref is None:
            logger.info(
                "KSeF GET returned empty results, trying POST query fallback"
            )
            query_path_candidates = [
                f"/sessions/{session_reference}/invoices/query",
                "/invoices/query",
            ]
            query_body = {
                "queryCriteria": {
                    "invoiceType": "received",
                    "subjectType": subject_type,
                    "invoicingDateFrom": invoicing_date_from,
                    "invoicingDateTo": invoicing_date_to,
                },
            }
            # DIAGNOSTICS: log POST body (no tokens/certs)
            logger.info(
                "KSeF query_received_invoices POST fallback: subjectType=%s body_keys=%s "
                "invoiceReferenceNumber_in_body=%s",
                subject_type,
                list(query_body.get("queryCriteria", {}).keys()),
                "invoiceReferenceNumber" in query_body.get("queryCriteria", {}),
            )
            # Pomijamy 400 z exceptionCode 21405 (bad invoiceReferenceNumber) — oznacza
            # że endpoint używa innej semantyki URL niż query listy zakupów.
            _SKIP_STATUS_CODES = frozenset({404, 405})
            post_fallback_attempted = True
            post_fallback_only_skipable = True
            for candidate in query_path_candidates:
                logger.info(
                    "KSeF query_received_invoices POST attempt: endpoint=%s",
                    candidate,
                )
                try:
                    resp = self._request_with_retry(
                        method="POST",
                        path=candidate,
                        headers=headers,
                        json=query_body,
                    )
                    poll_path_prefix = candidate
                    query_ref = resp.json()["referenceNumber"]
                    logger.info("KSeF query received invoices: queryRef=%s", query_ref)
                    break
                except KSeFClientError as exc:
                    # Pomijamy 400 z exceptionCode 21405 (zły invoiceReferenceNumber
                    # w URL) lub standardowe 404/405 (endpoint niedostępny).
                    if (
                        exc.status_code not in _SKIP_STATUS_CODES
                        and not _is_wrong_invoice_reference_error(exc)
                    ):
                        raise
                    last_exc = exc
                    logger.warning(
                        "KSeF query endpoint %s unavailable (%s), trying next fallback",
                        candidate,
                        exc.status_code,
                    )

        if not invoice_refs and query_ref is None:
            if (
                empty_get_succeeded
                and post_fallback_attempted
                and post_fallback_only_skipable
            ):
                logger.info(
                    "KSeF received invoices query returned empty result; "
                    "no POST query endpoint available"
                )
                return []
            raise last_exc or KSeFClientError("Brak dostępnego endpointu query dla KSeF.")

        # 3. Polling query reference — max 60s co 3s
        if query_ref is not None and poll_path_prefix is not None:
            invoice_refs = []
            for _attempt in range(20):
                time.sleep(3)
                try:
                    poll_resp = self._request_with_retry(
                        method="GET",
                        path=f"{poll_path_prefix}/{query_ref}",
                        headers=headers,
                    )
                except KSeFClientError as exc:
                    if exc.status_code == 202:
                        # Jeszcze przetwarza — czekamy
                        continue
                    raise
                data = poll_resp.json()
                code = data.get("processingCode", 0)
                if code == 200:
                    invoice_refs = [
                        inv["ksefReferenceNumber"]
                        for inv in data.get("invoiceList", [])
                    ]
                    logger.info(
                        "KSeF query done: queryRef=%s, count=%d", query_ref, len(invoice_refs)
                    )
                    break
                if code >= 400:
                    raise KSeFClientError(
                        f"KSeF query zakończone błędem: code={code}",
                        status_code=code,
                    )

        # 3. Pobierz i odszyfruj każdą fakturę (legacy — sesyjny fallback)
        return self._download_legacy_session_invoices(
            access_token=access_token,
            invoice_refs=invoice_refs,
            symmetric_key=symmetric_key,
            iv=iv,
        )

    def _query_purchase_metadata_refs(
        self,
        *,
        access_token: str,
        date_from: str,
        date_to: str,
    ) -> list[str] | None:
        """Zwraca listę ksefNumber z POST /invoices/query/metadata lub None gdy endpoint niedostępny."""
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        from_dt = _format_metadata_datetime(date_from, end_of_day=False)
        to_dt = _format_metadata_datetime(date_to, end_of_day=True)

        refs: list[str] = []
        date_type_used: str | None = None

        for date_type in _METADATA_DATE_TYPES:
            page_offset = 0
            batch_refs: list[str] = []
            while True:
                body = {
                    "subjectType": _METADATA_SUBJECT_PURCHASE,
                    "dateRange": {
                        "dateType": date_type,
                        "from": from_dt,
                        "to": to_dt,
                    },
                }
                try:
                    self._pace_purchase_request()
                    resp = self._request_with_retry(
                        method="POST",
                        path="/invoices/query/metadata",
                        headers=headers,
                        params={"pageOffset": page_offset, "pageSize": _METADATA_PAGE_SIZE},
                        json=body,
                    )
                except KSeFClientError as exc:
                    if exc.status_code in (404, 405):
                        logger.info(
                            "KSeF metadata query unavailable (%s), using session fallback",
                            exc.status_code,
                        )
                        return None
                    raise

                self._mark_purchase_request()
                data = resp.json()
                page_refs = _extract_metadata_invoice_refs(data)
                batch_refs.extend(page_refs)

                has_more = data.get("hasMore") is True
                page_offset += _METADATA_PAGE_SIZE
                if not has_more or not page_refs:
                    break

            if batch_refs:
                refs = batch_refs
                date_type_used = date_type
                break

        if date_type_used:
            logger.info(
                "KSeF metadata query subjectType=%s dateType=%s refs=%d",
                _METADATA_SUBJECT_PURCHASE,
                date_type_used,
                len(refs),
            )

        # Dedup zachowując kolejność
        seen: set[str] = set()
        unique: list[str] = []
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                unique.append(ref)
        return unique

    def _download_metadata_purchase_invoices(
        self,
        *,
        access_token: str,
        invoice_refs: list[str],
    ) -> list[ReceivedInvoiceResult]:
        """Subject2 + metadata: oficjalny GET /invoices/ksef/{ksefNumber} → raw XML."""
        results: list[ReceivedInvoiceResult] = []
        for ref in invoice_refs:
            try:
                self._pace_purchase_request()
                inv_resp = self._request_with_retry(
                    method="GET",
                    path=f"/invoices/ksef/{ref}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/xml",
                    },
                )
                xml_bytes = inv_resp.content
                if not xml_bytes:
                    raise KSeFClientError(f"Pusta odpowiedź GET /invoices/ksef/{ref}")
                self._mark_purchase_request()
                results.append(ReceivedInvoiceResult(
                    ksef_reference_number=ref,
                    xml_bytes=xml_bytes,
                ))
            except Exception as exc:  # noqa: BLE001
                logger.warning("KSeF: błąd pobierania faktury %s: %s", ref, exc)
        return results

    def _download_legacy_session_invoices(
        self,
        *,
        access_token: str,
        invoice_refs: list[str],
        symmetric_key: bytes,
        iv: bytes,
    ) -> list[ReceivedInvoiceResult]:
        """Legacy sesyjny fallback: GET /invoices/{ref} + decrypt AES kluczem sesji."""
        results: list[ReceivedInvoiceResult] = []
        for ref in invoice_refs:
            try:
                inv_resp = self._request_with_retry(
                    method="GET",
                    path=f"/invoices/{ref}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                xml_bytes = self._parse_invoice_content(inv_resp.json(), symmetric_key, iv)
                results.append(ReceivedInvoiceResult(
                    ksef_reference_number=ref,
                    xml_bytes=xml_bytes,
                ))
            except Exception as exc:  # noqa: BLE001
                logger.warning("KSeF: błąd pobierania faktury %s: %s", ref, exc)
        return results

    @staticmethod
    def _parse_invoice_content(data: dict, symmetric_key: bytes, iv: bytes) -> bytes:
        if "encryptedInvoiceContent" in data:
            enc_content = base64.b64decode(data["encryptedInvoiceContent"])
            return _aes_cbc_decrypt(enc_content, symmetric_key, iv)
        for key in ("invoice", "invoiceXml", "invoiceFile"):
            raw = data.get(key)
            if isinstance(raw, str) and raw:
                try:
                    return base64.b64decode(raw)
                except Exception:  # noqa: BLE001
                    return raw.encode()
        raise KSeFClientError(
            "Nieznany format odpowiedzi GET /invoices/{ref} — brak encryptedInvoiceContent/invoice"
        )

    def get_upo(self, upo_url: str) -> bytes:
        """Pobiera UPO z URL zwróconego w statusie faktury (bez uwierzytelnienia)."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(upo_url)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            raise KSeFClientError(
                f"KSeF UPO download error ({exc.response.status_code}): "
                f"{exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise KSeFClientError(
                f"KSeF UPO connection error: {exc}",
                transient=True,
            ) from exc

    def check_connectivity(self) -> None:
        """Lekki probe dostępności KSeF bez wymagania aktywnej sesji."""
        self._fetch_symmetric_key_encryption_cert()

    # -------------------------------------------------------------------------
    # ENCRYPTION HELPERS
    # -------------------------------------------------------------------------

    def _fetch_symmetric_key_encryption_cert(self) -> bytes:
        """Pobiera certyfikat MF do szyfrowania klucza symetrycznego (DER)."""
        url = f"{self._base_url}/security/public-key-certificates"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
            resp.raise_for_status()
            certs = resp.json()
        except httpx.HTTPStatusError as exc:
            raise KSeFClientError(
                f"KSeF public key fetch error ({exc.response.status_code})",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise KSeFClientError(
                f"KSeF connection error: {exc}", transient=True
            ) from exc

        for cert_info in certs:
            if _USAGE_SYMMETRIC_KEY in cert_info.get("usage", []):
                return base64.b64decode(cert_info["certificate"])

        raise KSeFClientError(
            f"Nie znaleziono certyfikatu KSeF o użyciu '{_USAGE_SYMMETRIC_KEY}'."
        )

    def _encrypt_symmetric_key(self, symmetric_key: bytes) -> bytes:
        """Szyfruje klucz symetryczny RSA-OAEP (SHA-256) kluczem publicznym MF."""
        cert_der = self._fetch_symmetric_key_encryption_cert()
        cert = load_der_x509_certificate(cert_der)
        public_key = cert.public_key()
        return public_key.encrypt(
            symmetric_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

    # -------------------------------------------------------------------------
    # INTERNAL RETRY LOGIC
    # -------------------------------------------------------------------------

    def _pace_purchase_request(self) -> None:
        """Min. 1.2 s między requestami metadata/download zakupów (invoiceMetadata/invoiceDownload)."""
        if self._last_purchase_request_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_purchase_request_monotonic
        if elapsed < _REQUEST_MIN_INTERVAL:
            time.sleep(_REQUEST_MIN_INTERVAL - elapsed)

    def _mark_purchase_request(self) -> None:
        self._last_purchase_request_monotonic = time.monotonic()

    def _request_with_retry(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        **kwargs,
    ):
        url = self._base_url + path
        last_exc: Exception | None = None

        for attempt in range(self._retry.max_retries + 1):
            if attempt > 0:
                backoff = min(
                    self._retry.backoff_base * (2 ** (attempt - 1))
                    + random.uniform(0, 0.1 * self._retry.backoff_base),
                    self._retry.backoff_max,
                )
                logger.warning(
                    "KSeF retry: attempt=%s/%s backoff=%.2fs url=%s",
                    attempt,
                    self._retry.max_retries,
                    backoff,
                    url,
                )
                time.sleep(backoff)

            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.request(method, url, headers=headers, **kwargs)

                if response.status_code in _SUCCESS_STATUS_CODES:
                    return response

                if response.status_code in (401, 403):
                    raise KSeFSessionExpiredError(
                        f"KSeF: token wygasł lub nieautoryzowany "
                        f"({response.status_code}): {response.text[:200]}",
                        status_code=response.status_code,
                    )

                transient = response.status_code in _TRANSIENT_STATUS_CODES
                last_exc = KSeFClientError(
                    f"KSeF odpowiedział statusem {response.status_code}: "
                    f"{response.text[:200]}",
                    status_code=response.status_code,
                    transient=transient,
                )

                if not transient:
                    raise last_exc

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            sleep_secs = max(float(retry_after), _REQUEST_MIN_INTERVAL)
                        except ValueError:
                            sleep_secs = _REQUEST_MIN_INTERVAL
                        time.sleep(sleep_secs)
                    else:
                        time.sleep(_REQUEST_MIN_INTERVAL)

            except KSeFClientError:
                raise
            except httpx.TimeoutException as exc:
                last_exc = KSeFClientError(
                    f"KSeF: timeout po {self._timeout}s: {exc}",
                    transient=True,
                )
            except httpx.RequestError as exc:
                last_exc = KSeFClientError(
                    f"KSeF: błąd połączenia: {exc}",
                    transient=True,
                )

        raise last_exc or KSeFClientError(
            "KSeF: wyczerpano liczbę prób (nie powiodła się żadna).",
            transient=True,
        )


# -------------------------------------------------------------------------
# STANDALONE CRYPTO HELPERS
# -------------------------------------------------------------------------

def _aes_cbc_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    """Szyfruje dane AES-256-CBC z dopełnieniem PKCS#7."""
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def _aes_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """Odszyfrowuje dane AES-256-CBC z dopełnieniem PKCS#7."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()
