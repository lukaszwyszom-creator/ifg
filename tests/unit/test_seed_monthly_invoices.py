from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_seed_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_monthly_invoices.py"
    spec = importlib.util.spec_from_file_location("seed_monthly_invoices", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class TestSeedMonthlyInvoices:
    def test_post_invoice_calls_mark_ready(self, monkeypatch):
        mod = _load_seed_module()

        create_called = {"value": False}
        mark_called = {"value": False}

        def fake_post(url, json=None, headers=None, timeout=None):
            if url.endswith("/api/v1/invoices/"):
                create_called["value"] = True
                return _Resp(201, {
                    "id": "inv-1",
                    "number_local": None,
                    "total_gross": "123.00",
                    "currency": "PLN",
                    "issue_date": "2026-04-01",
                })
            if url.endswith("/api/v1/invoices/inv-1/mark-ready"):
                mark_called["value"] = True
                return _Resp(200, {
                    "id": "inv-1",
                    "number_local": "FV/1/04/2026",
                    "total_gross": "123.00",
                    "currency": "PLN",
                    "issue_date": "2026-04-01",
                })
            return _Resp(404, text="not found")

        monkeypatch.setattr(mod.requests, "post", fake_post)

        result = mod.post_invoice("token", {"foo": "bar"})

        assert create_called["value"] is True
        assert mark_called["value"] is True
        assert result is not None
        assert result["number_local"] == "FV/1/04/2026"

    def test_post_seed_quality_check_detects_missing_fields(self, monkeypatch):
        mod = _load_seed_module()

        def fake_get(url, headers=None, timeout=None):
            return _Resp(200, {
                "id": "inv-1",
                "number_local": "",
                "seller_snapshot": {"name": "", "nip": ""},
                "buyer_snapshot": {"name": "Buyer", "nip": ""},
            })

        monkeypatch.setattr(mod.requests, "get", fake_get)

        errors = mod.post_seed_quality_check("token", [{"id": "inv-1"}])

        assert any("number_local" in e for e in errors)
        assert any("seller_snapshot.name" in e for e in errors)
        assert any("seller_snapshot.nip" in e for e in errors)
        assert any("buyer_snapshot.nip" in e for e in errors)

    def test_main_exits_with_error_when_quality_check_fails(self, monkeypatch):
        mod = _load_seed_module()

        monkeypatch.setattr(mod, "login", lambda: "token")
        monkeypatch.setattr(mod, "SALE_MARCH", [])
        monkeypatch.setattr(mod, "SALE_APRIL", [])
        monkeypatch.setattr(mod, "PURCHASE_MARCH", [])
        monkeypatch.setattr(mod, "PURCHASE_APRIL", [])
        monkeypatch.setattr(mod, "post_invoice", lambda token, data: {"id": "inv-1"})
        monkeypatch.setattr(mod, "post_seed_quality_check", lambda token, created: ["err"])

        class ExitCalled(Exception):
            pass

        def fake_exit(code):
            raise ExitCalled(code)

        monkeypatch.setattr(mod.sys, "exit", fake_exit)

        try:
            mod.main()
            assert False, "Expected exit"
        except ExitCalled as exc:
            assert exc.args[0] == 1
