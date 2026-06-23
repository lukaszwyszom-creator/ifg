"""Paginacja metadata KSeF — zakupy Subject2."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.integrations.ksef.client import KSeFClient, RetryConfig


def _make_client() -> KSeFClient:
    return KSeFClient(
        environment="production",
        timeout_seconds=5,
        retry_config=RetryConfig(max_retries=0, backoff_base=0.0, backoff_max=0.0),
    )


def _refs(count: int, *, start: int = 0, prefix: str = "NIP") -> list[dict]:
    return [{"ksefNumber": f"{prefix}-20260330-{idx:04d}"} for idx in range(start, start + count)]


def _run_metadata_query(
    client: KSeFClient,
    *,
    pages_by_date_type: dict[str, dict[int, dict]],
) -> list[str]:
    """pages_by_date_type: dateType -> {pageOffset -> response dict}."""

    def _fake_request(method, url, *, headers=None, params=None, json=None, **kw):
        assert method == "POST"
        assert "/invoices/query/metadata" in url
        date_type = json["dateRange"]["dateType"]
        offset = int((params or {}).get("pageOffset", 0))
        pages = pages_by_date_type.get(date_type, {})
        payload = pages.get(offset, {"hasMore": False, "invoices": []})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        return resp

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.request.side_effect = _fake_request

    with patch("httpx.Client", return_value=ctx), patch.object(client, "_pace_purchase_request"), patch.object(
        client, "_mark_purchase_request"
    ):
        return client.query_purchase_metadata_refs(
            access_token="tok",
            date_from="2026-03-23",
            date_to="2026-06-21",
        )


class TestMetadataPagination:
    def test_two_pages_return_70_refs(self) -> None:
        client = _make_client()
        refs = _run_metadata_query(
            client,
            pages_by_date_type={
                "PermanentStorage": {
                    0: {"hasMore": True, "invoices": _refs(50)},
                    50: {"hasMore": False, "invoices": _refs(20, start=50)},
                },
                "Invoicing": {},
                "Issue": {},
            },
        )
        assert len(refs) == 70

    def test_full_first_page_with_has_more_false_still_fetches_next_page(self) -> None:
        client = _make_client()
        refs = _run_metadata_query(
            client,
            pages_by_date_type={
                "PermanentStorage": {
                    0: {"hasMore": False, "invoices": _refs(50)},
                    50: {"hasMore": False, "invoices": _refs(20, start=50)},
                },
                "Invoicing": {},
                "Issue": {},
            },
        )
        assert len(refs) == 70

    def test_second_page_empty_ends_with_first_page_only(self) -> None:
        client = _make_client()
        refs = _run_metadata_query(
            client,
            pages_by_date_type={
                "PermanentStorage": {
                    0: {"hasMore": True, "invoices": _refs(50)},
                    50: {"hasMore": False, "invoices": []},
                },
                "Invoicing": {},
                "Issue": {},
            },
        )
        assert len(refs) == 50

    def test_permanent_storage_and_invoicing_union_deduped(self) -> None:
        client = _make_client()
        refs = _run_metadata_query(
            client,
            pages_by_date_type={
                "PermanentStorage": {
                    0: {"hasMore": False, "invoices": [{"ksefNumber": "SHARED-REF"}]},
                },
                "Invoicing": {
                    0: {
                        "hasMore": False,
                        "invoices": [
                            {"ksefNumber": "SHARED-REF"},
                            {"ksefNumber": "INVOICING-ONLY"},
                        ],
                    },
                },
                "Issue": {},
            },
        )
        assert refs == ["SHARED-REF", "INVOICING-ONLY"]
