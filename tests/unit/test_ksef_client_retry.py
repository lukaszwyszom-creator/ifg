"""Testy KSeFClient — retry, backoff, klasyfikacja błędów."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.integrations.ksef.client import KSeFClient, KSeFClientError, RetryConfig


@pytest.fixture()
def client() -> KSeFClient:
    return KSeFClient(
        environment="test",
        timeout_seconds=5,
        retry_config=RetryConfig(max_retries=2, backoff_base=0.01, backoff_max=0.05),
    )


def _send_args() -> tuple[str, str, bytes, bytes, bytes]:
    return ("token", "sess-ref", b"k" * 32, b"i" * 16, b"<xml/>")


class TestKSeFClientRetry:
    def test_success_no_retry(self, client: KSeFClient):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "referenceNumber": "REF-1",
        }

        with patch("httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.request.return_value = response
            mock_client_cls.return_value = ctx

            result = client.send_invoice(*_send_args())

        assert result.reference_number == "REF-1"
        assert ctx.request.call_count == 1

    def test_transient_error_retries_then_succeeds(self, client: KSeFClient):
        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.text = "Service Unavailable"

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "referenceNumber": "REF-2",
        }

        with patch("httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.request.side_effect = [fail_resp, ok_resp]
            mock_client_cls.return_value = ctx

            result = client.send_invoice(*_send_args())

        assert result.reference_number == "REF-2"
        assert ctx.request.call_count == 2

    def test_permanent_error_no_retry(self, client: KSeFClient):
        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.text = "Bad Request"

        with patch("httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.request.return_value = fail_resp
            mock_client_cls.return_value = ctx

            with pytest.raises(KSeFClientError) as exc_info:
                client.send_invoice(*_send_args())

        assert exc_info.value.transient is False
        assert exc_info.value.status_code == 400
        assert ctx.request.call_count == 1

    def test_timeout_retries(self, client: KSeFClient):
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "referenceNumber": "REF-3",
        }

        with patch("httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.request.side_effect = [
                httpx.TimeoutException("Read timed out"),
                ok_resp,
            ]
            mock_client_cls.return_value = ctx

            result = client.send_invoice(*_send_args())

        assert result.reference_number == "REF-3"
        assert ctx.request.call_count == 2

    def test_all_retries_exhausted(self, client: KSeFClient):
        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.text = "Service Unavailable"

        with patch("httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.request.return_value = fail_resp
            mock_client_cls.return_value = ctx

            with pytest.raises(KSeFClientError) as exc_info:
                client.send_invoice(*_send_args())

        assert exc_info.value.transient is True
        assert ctx.request.call_count == 3

    def test_transient_flag_on_error(self):
        err_transient = KSeFClientError("err", status_code=503, transient=True)
        assert err_transient.transient is True

        err_permanent = KSeFClientError("err", status_code=400, transient=False)
        assert err_permanent.transient is False


class TestKSeFClientGetInvoiceStatus:
    """Commit 10: kontrakt i retry dla get_invoice_status."""

    def _make_client(self) -> KSeFClient:
        return KSeFClient(
            environment="test",
            timeout_seconds=5,
            retry_config=RetryConfig(max_retries=2, backoff_base=0.01, backoff_max=0.05),
        )

    def _ctx(self, mock_client_cls, side_effects):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.request.side_effect = side_effects
        mock_client_cls.return_value = ctx
        return ctx

    def test_returns_invoice_status_result(self):
        client = self._make_client()
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "ksefNumber": "KSeF/001/2026",
            "upoDownloadUrl": "https://upo.test/ok",
        }
        with patch("httpx.Client") as mock_cls:
            self._ctx(mock_cls, [ok_resp])
            result = client.get_invoice_status("tok", "sess-ref", "REF-1")

        assert result.processing_code == 200
        assert result.ksef_reference_number == "KSeF/001/2026"
        assert result.upo_url == "https://upo.test/ok"

    def test_failed_invoice_returns_detailed_rejection_message(self):
        client = self._make_client()
        ok = MagicMock(status_code=200)
        ok.json.return_value = {"ksefNumber": None}
        failed_list = MagicMock(status_code=200)
        failed_list.json.return_value = {
            "invoices": [
                {
                    "referenceNumber": "REF-FAIL",
                    "status": {
                        "code": 440,
                        "description": "Duplikat faktury",
                        "details": [
                            "Duplikat faktury. Faktura o numerze KSeF: 5265877635-20250626-010080DD2B5E-26"
                        ],
                    },
                }
            ]
        }

        with patch("httpx.Client") as mock_cls:
            self._ctx(mock_cls, [ok, failed_list])
            result = client.get_invoice_status("tok", "sess-ref", "REF-FAIL")

        assert result.processing_code == 400
        assert "Duplikat faktury" in result.processing_description
        assert "5265877635" in result.processing_description

    def test_transient_error_retries(self):
        client = self._make_client()
        fail = MagicMock(status_code=503, text="overload")
        ok = MagicMock(status_code=200)
        ok.json.return_value = {"ksefNumber": None}
        failed_list = MagicMock(status_code=200)
        failed_list.json.return_value = {"invoices": []}

        with patch("httpx.Client") as mock_cls:
            ctx = self._ctx(mock_cls, [fail, ok, failed_list])
            result = client.get_invoice_status("tok", "sess-ref", "REF-2")

        assert result.processing_code == 100
        assert result.ksef_reference_number is None
        assert ctx.request.call_count == 3

    def test_ksef_reference_number_can_be_none(self):
        """Przy statusie in-queue ksef_reference_number może być null."""
        client = self._make_client()
        ok = MagicMock(status_code=200)
        ok.json.return_value = {"ksefNumber": None}
        failed_list = MagicMock(status_code=200)
        failed_list.json.return_value = {"invoices": []}

        with patch("httpx.Client") as mock_cls:
            self._ctx(mock_cls, [ok, failed_list])
            result = client.get_invoice_status("tok", "sess-ref", "REF-3")

        assert result.ksef_reference_number is None


class TestKSeFClientGetUPO:
    """Commit 10: kontrakt get_upo."""

    def test_returns_bytes(self):
        client = KSeFClient(environment="test", timeout_seconds=5)
        ok = MagicMock(status_code=200, content=b"<UPO>content</UPO>")
        ok.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = ok
            mock_cls.return_value = ctx
            result = client.get_upo("https://upo.test/123")

        assert result == b"<UPO>content</UPO>"

    def test_error_raises_ksef_client_error(self):
        client = KSeFClient(
            environment="test",
            timeout_seconds=5,
            retry_config=RetryConfig(max_retries=0),
        )
        fail = MagicMock(status_code=404, text="Not found")
        fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404",
            request=MagicMock(),
            response=fail,
        )

        with patch("httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.get.return_value = fail
            mock_cls.return_value = ctx
            with pytest.raises(KSeFClientError) as exc_info:
                client.get_upo("https://upo.test/404")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Testy query_received_invoices — brak invoiceReferenceNumber w zapytaniach
# ---------------------------------------------------------------------------

class TestQueryReceivedInvoicesNoInvoiceReferenceNumber:
    """Pilnuje, że sync listy zakupów nigdy nie wysyła invoiceReferenceNumber."""

    @staticmethod
    def _maybe_metadata_404(method: str, url: str):
        if method == "POST" and "/invoices/query/metadata" in url:
            resp = MagicMock()
            resp.status_code = 404
            resp.text = "Not Found"
            return resp
        return None

    @staticmethod
    def _maybe_post_query_404(method: str, url: str):
        if method == "POST" and "/invoices/query" in url and "/metadata" not in url:
            resp = MagicMock()
            resp.status_code = 404
            resp.text = "Not Found"
            return resp
        return None

    def _make_client(self) -> KSeFClient:
        return KSeFClient(
            environment="test",
            timeout_seconds=5,
            retry_config=RetryConfig(max_retries=0, backoff_base=0.0, backoff_max=0.0),
        )

    def _mock_ctx(self):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    def test_get_candidates_do_not_include_invoice_reference_number(self):
        """Żaden GET candidate nie wysyła invoiceReferenceNumber w params."""
        client = self._make_client()

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"invoices": []}  # pusta lista — brak faktur

        recorded_calls: list[dict] = []

        def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
            meta = TestQueryReceivedInvoicesNoInvoiceReferenceNumber._maybe_metadata_404(method, url)
            if meta is not None:
                return meta
            post_q = TestQueryReceivedInvoicesNoInvoiceReferenceNumber._maybe_post_query_404(method, url)
            if post_q is not None:
                return post_q
            recorded_calls.append({"method": method, "url": url, "params": params or {}, "json": json or {}})
            return ok_resp

        with patch("httpx.Client") as mock_cls:
            ctx = self._mock_ctx()
            ctx.request.side_effect = _fake_request
            mock_cls.return_value = ctx

            client.query_received_invoices(
                access_token="tok",
                session_reference="sess-ref",
                symmetric_key=b"k" * 32,
                iv=b"i" * 16,
                invoicing_date_from="2026-05-01",
                invoicing_date_to="2026-05-31",
            )

        for call in recorded_calls:
            assert "invoiceReferenceNumber" not in call["params"], (
                f"invoiceReferenceNumber nie powinno być w params GET {call['url']}"
            )
            assert "invoiceReferenceNumber" not in call["json"], (
                f"invoiceReferenceNumber nie powinno być w body POST {call['url']}"
            )

    def test_post_fallback_does_not_include_invoice_reference_number(self):
        """POST fallback query nie wysyła invoiceReferenceNumber w body."""
        client = self._make_client()

        # Wszystkie GET candidates → 404
        not_found = MagicMock()
        not_found.status_code = 404
        not_found.text = "Not Found"

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"referenceNumber": "qref-1", "processingCode": 200, "invoiceList": []}

        recorded_post_calls: list[dict] = []

        call_count = [0]

        def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
            meta = TestQueryReceivedInvoicesNoInvoiceReferenceNumber._maybe_metadata_404(method, url)
            if meta is not None:
                return meta
            call_count[0] += 1
            if method == "GET" and "/invoices" in url and "query" not in url and "received" not in url:
                # polling call after query_ref set
                return ok_resp
            if method == "GET":
                return not_found
            # POST
            recorded_post_calls.append({"method": method, "url": url, "json": json or {}})
            return ok_resp

        with patch("httpx.Client") as mock_cls:
            ctx = self._mock_ctx()
            ctx.request.side_effect = _fake_request
            mock_cls.return_value = ctx

            client.query_received_invoices(
                access_token="tok",
                session_reference="sess-ref",
                symmetric_key=b"k" * 32,
                iv=b"i" * 16,
                invoicing_date_from="2026-05-01",
                invoicing_date_to="2026-05-31",
            )

        for call in recorded_post_calls:
            body = call["json"]
            criteria = body.get("queryCriteria", {})
            assert "invoiceReferenceNumber" not in criteria, (
                f"invoiceReferenceNumber nie powinno być w queryCriteria POST {call['url']}"
            )
            assert "invoiceReferenceNumber" not in body, (
                f"invoiceReferenceNumber nie powinno być w body POST {call['url']}"
            )

    def test_post_fallback_does_not_use_sessions_online_invoices_query_path(self):
        """Sprawdza, że /sessions/online/{ref}/invoices/query NIE jest w POST fallback.

        Ten path był przyczyną błędu 400 / exceptionCode 21405 — KSeF interpretował
        'query' jako invoiceReferenceNumber w URL /sessions/online/{ref}/invoices/{ref}.
        """
        client = self._make_client()

        # Wszystkie GET → 404
        not_found = MagicMock()
        not_found.status_code = 404
        not_found.text = "Not Found"

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"referenceNumber": "qref-2", "processingCode": 200, "invoiceList": []}

        recorded_urls: list[str] = []

        def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
            meta = TestQueryReceivedInvoicesNoInvoiceReferenceNumber._maybe_metadata_404(method, url)
            if meta is not None:
                return meta
            recorded_urls.append(url)
            if method == "GET":
                return not_found
            return ok_resp

        with patch("httpx.Client") as mock_cls:
            ctx = self._mock_ctx()
            ctx.request.side_effect = _fake_request
            mock_cls.return_value = ctx

            try:
                client.query_received_invoices(
                    access_token="tok",
                    session_reference="sess-ref",
                    symmetric_key=b"k" * 32,
                    iv=b"i" * 16,
                    invoicing_date_from="2026-05-01",
                    invoicing_date_to="2026-05-31",
                )
            except KSeFClientError:
                pass  # może nie być żadnego działającego endpointu w teście

        bad_path = "/sessions/online/sess-ref/invoices/query"
        base_url = "https://api-test.ksef.mf.gov.pl/v2"
        assert f"{base_url}{bad_path}" not in recorded_urls, (
            "POST /sessions/online/{ref}/invoices/query NIE powinien być wywoływany "
            "(powoduje błąd KSeF 400 / exceptionCode 21405)"
        )

    def test_get_candidate_400_21405_falls_back_without_invoice_reference_number(self):
        """GET endpoint interpretowany jako invoiceReferenceNumber nie kończy synca."""
        client = self._make_client()

        wrong_ref = MagicMock()
        wrong_ref.status_code = 400
        wrong_ref.text = (
            '{"exception":{"exceptionDetailList":[{"exceptionCode":21405,'
            '"details":["\'invoiceReferenceNumber\' is not in the correct format"]}]}}'
        )

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"invoices": []}

        recorded_calls: list[dict] = []

        def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
            meta = TestQueryReceivedInvoicesNoInvoiceReferenceNumber._maybe_metadata_404(method, url)
            if meta is not None:
                return meta
            post_q = TestQueryReceivedInvoicesNoInvoiceReferenceNumber._maybe_post_query_404(method, url)
            if post_q is not None:
                return post_q
            recorded_calls.append({"method": method, "url": url, "params": params or {}, "json": json or {}})
            if method == "GET" and len(recorded_calls) == 1:
                return wrong_ref
            return ok_resp

        with patch("httpx.Client") as mock_cls:
            ctx = self._mock_ctx()
            ctx.request.side_effect = _fake_request
            mock_cls.return_value = ctx

            client.query_received_invoices(
                access_token="tok",
                session_reference="sess-ref",
                symmetric_key=b"k" * 32,
                iv=b"i" * 16,
                invoicing_date_from="2026-05-01",
                invoicing_date_to="2026-05-31",
            )

        assert len(recorded_calls) >= 2
        for call in recorded_calls:
            assert "invoiceReferenceNumber" not in call["params"]
            assert "invoiceReferenceNumber" not in call["json"]


class TestQueryReceivedInvoicesMetadata:
    """Zakupy Subject2 przez POST /invoices/query/metadata (prod KSeF v2)."""

    def _make_client(self) -> KSeFClient:
        return KSeFClient(
            environment="production",
            timeout_seconds=5,
            retry_config=RetryConfig(max_retries=0, backoff_base=0.0, backoff_max=0.0),
        )

    def test_subject2_uses_metadata_query_and_official_ksef_download_path(self):
        client = self._make_client()

        metadata_resp = MagicMock()
        metadata_resp.status_code = 200
        metadata_resp.json.return_value = {
            "hasMore": False,
            "invoices": [{"ksefNumber": "KSEF-META-1"}],
        }

        invoice_resp = MagicMock()
        invoice_resp.status_code = 200
        invoice_resp.content = b'<?xml version="1.0"?><Faktura><numer>1</numer></Faktura>'

        recorded_posts: list[dict] = []
        recorded_gets: list[str] = []

        def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
            if method == "POST" and "/invoices/query/metadata" in url:
                recorded_posts.append({"json": json, "params": params})
                return metadata_resp
            if method == "GET" and "/invoices/ksef/KSEF-META-1" in url:
                recorded_gets.append(url)
                assert headers.get("Accept") == "application/xml"
                return invoice_resp
            if method == "GET" and "/invoices/KSEF-META-1" in url:
                raise AssertionError(f"Użyto nieoficjalnego path bez /ksef/: {url}")
            raise AssertionError(f"Unexpected request: {method} {url}")

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.request.side_effect = _fake_request

        with patch("httpx.Client", return_value=ctx):
            results = client.query_received_invoices(
                access_token="tok",
                session_reference="sess-ref",
                symmetric_key=b"k" * 32,
                iv=b"i" * 16,
                invoicing_date_from="2026-05-01",
                invoicing_date_to="2026-06-09",
                subject_type="subject2",
            )

        assert len(recorded_posts) == 1
        body = recorded_posts[0]["json"]
        assert body["subjectType"] == "Subject2"
        assert body["dateRange"]["dateType"] == "PermanentStorage"
        assert body["dateRange"]["from"] == "2026-05-01T00:00:00Z"
        assert body["dateRange"]["to"] == "2026-06-09T23:59:59Z"
        assert len(recorded_gets) == 1
        assert "/invoices/ksef/KSEF-META-1" in recorded_gets[0]
        assert len(results) == 1
        assert results[0].ksef_reference_number == "KSEF-META-1"
        assert b"Faktura" in results[0].xml_bytes

    def test_subject1_session_fallback_uses_legacy_path_not_ksef(self):
        client = self._make_client()

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {
            "invoices": [{"ksefReferenceNumber": "LEGACY-1"}],
        }

        legacy_invoice_resp = MagicMock()
        legacy_invoice_resp.status_code = 200
        legacy_invoice_resp.json.return_value = {"invoice": "PHhtbC8vPg=="}  # "<xml/>"

        recorded_gets: list[str] = []

        def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
            if method == "POST" and "/invoices/query/metadata" in url:
                raise AssertionError("metadata nie powinno być wywoływane dla subject1")
            if method == "GET" and "/sessions/" in url:
                return session_resp
            if method == "GET" and "/invoices/" in url:
                recorded_gets.append(url)
                if "/invoices/ksef/" in url:
                    raise AssertionError(f"legacy fallback nie powinien używać /ksef/: {url}")
                return legacy_invoice_resp
            raise AssertionError(f"Unexpected request: {method} {url}")

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.request.side_effect = _fake_request

        with patch("httpx.Client", return_value=ctx):
            results = client.query_received_invoices(
                access_token="tok",
                session_reference="sess-ref",
                symmetric_key=b"k" * 32,
                iv=b"i" * 16,
                invoicing_date_from="2026-05-01",
                invoicing_date_to="2026-06-09",
                subject_type="subject1",
            )

        assert len(results) == 1
        assert results[0].ksef_reference_number == "LEGACY-1"
        assert any("/invoices/LEGACY-1" in u and "/ksef/" not in u for u in recorded_gets)
