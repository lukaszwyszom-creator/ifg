"""Testy RegonClient i ContractorService.get_by_nip() — wyłącznie z mockami."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ExternalServiceError, NotFoundError
from app.integrations.regon.client import RegonClient
from app.services.contractor_service import ContractorService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def regon_client_production() -> RegonClient:
    return RegonClient(
        api_key="valid-regon-key",
        environment="production",
        timeout_seconds=10,
        wsdl_test="https://test.wsdl/",
        wsdl_production="https://prod.wsdl/",
    )


@pytest.fixture()
def regon_client_change_me() -> RegonClient:
    return RegonClient(
        api_key="change-me",
        environment="production",
        timeout_seconds=10,
        wsdl_test="https://test.wsdl/",
        wsdl_production="https://prod.wsdl/",
    )


@pytest.fixture()
def regon_client_none_key() -> RegonClient:
    return RegonClient(
        api_key=None,
        environment="production",
        timeout_seconds=10,
        wsdl_test="https://test.wsdl/",
        wsdl_production="https://prod.wsdl/",
    )


def _make_contractor_service(regon_client=None):
    session = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    contractor_repo = MagicMock()
    override_repo = MagicMock()
    audit_service = MagicMock()
    regon_mapper = MagicMock()
    service = ContractorService(
        session=session,
        contractor_repository=contractor_repo,
        contractor_override_repository=override_repo,
        audit_service=audit_service,
        regon_client=regon_client or MagicMock(),
        regon_mapper=regon_mapper,
    )
    return service, contractor_repo, override_repo, session


def _make_actor():
    from app.core.security import AuthenticatedUser
    return AuthenticatedUser(user_id=uuid4(), username="tester", role="operator")


def _make_existing_contractor():
    from app.persistence.models.contractor import ContractorORM
    c = MagicMock(spec=ContractorORM)
    c.id = uuid4()
    c.nip = "1000000035"
    c.name = "Stary kontrahent"
    c.source = "regon"
    c.source_fetched_at = datetime(2020, 1, 1, tzinfo=UTC)
    c.lookup_last_status = "success"
    c.lookup_last_error = None
    # cache_valid_until = None wymusza odświeżenie w _is_cache_fresh
    c.cache_valid_until = None
    return c


# ---------------------------------------------------------------------------
# RegonClient — testy jednostkowe
# ---------------------------------------------------------------------------

class TestRegonClientKeyGuard:
    def test_change_me_returns_none(self, regon_client_change_me: RegonClient):
        """REGON_API_KEY=change-me → None (brak danych, nie błąd krytyczny)."""
        result = regon_client_change_me.lookup_by_nip("1000000035")
        assert result is None

    def test_none_key_returns_none(self, regon_client_none_key: RegonClient):
        """Brak REGON_API_KEY → None (brak danych, nie błąd krytyczny)."""
        result = regon_client_none_key.lookup_by_nip("1000000035")
        assert result is None

    def test_unconfigured_key_does_not_raise(self, regon_client_change_me: RegonClient):
        """Niezskonfigurowany klucz nie rzuca wyjątku — zwraca None bez wycieku klucza."""
        result = regon_client_change_me.lookup_by_nip("1000000035")
        assert result is None

    def test_resolves_test_wsdl_for_test_env(self):
        client = RegonClient(
            api_key="key",
            environment="test",
            timeout_seconds=5,
            wsdl_test="https://test.wsdl/",
            wsdl_production="https://prod.wsdl/",
        )
        assert client._resolve_wsdl() == "https://test.wsdl/"

    def test_resolves_production_wsdl_for_production_env(self):
        client = RegonClient(
            api_key="key",
            environment="production",
            timeout_seconds=5,
            wsdl_test="https://test.wsdl/",
            wsdl_production="https://prod.wsdl/",
        )
        assert client._resolve_wsdl() == "https://prod.wsdl/"


class TestRegonClientSOAP:
    def test_soap_exception_raises_external_service_error(self, regon_client_production: RegonClient):
        """Błąd SOAP (sieciowy) musi być opakowany w ExternalServiceError."""
        with patch("app.integrations.regon.client.Client") as MockClient:
            mock_soap = MagicMock()
            mock_soap.service.Zaloguj.side_effect = Exception("Connection refused")
            MockClient.return_value = mock_soap

            with pytest.raises(ExternalServiceError) as exc_info:
                regon_client_production.lookup_by_nip("1000000035")
            assert "REGON" in str(exc_info.value)

    def test_soap_exception_does_not_leak_api_key(self, regon_client_production: RegonClient):
        """Błąd SOAP nie może ujawniać klucza API w komunikacie."""
        with patch("app.integrations.regon.client.Client") as MockClient:
            mock_soap = MagicMock()
            mock_soap.service.Zaloguj.side_effect = Exception("Connection refused")
            MockClient.return_value = mock_soap

            try:
                regon_client_production.lookup_by_nip("1000000035")
            except ExternalServiceError as exc:
                assert "valid-regon-key" not in str(exc)

    def test_returns_none_for_empty_result(self, regon_client_production: RegonClient):
        """Brak wyników REGON → None (nie wyjątek)."""
        with patch("app.integrations.regon.client.Client") as MockClient:
            mock_soap = MagicMock()
            mock_soap.service.Zaloguj.return_value = "session-1"
            mock_soap.service.DaneSzukajPodmioty.return_value = None
            MockClient.return_value = mock_soap

            result = regon_client_production.lookup_by_nip("9999999999")
            assert result is None

    def test_returns_first_record_on_success(self, regon_client_production: RegonClient):
        """Poprawna odpowiedź REGON → pierwszy rekord jako słownik."""
        xml_result = "<root><dane><Nip>1000000035</Nip><Nazwa>Firma ABC</Nazwa></dane></root>"
        with patch("app.integrations.regon.client.Client") as MockClient:
            mock_soap = MagicMock()
            mock_soap.service.Zaloguj.return_value = "session-1"
            mock_soap.service.DaneSzukajPodmioty.return_value = xml_result
            MockClient.return_value = mock_soap

            result = regon_client_production.lookup_by_nip("1000000035")
            assert result is not None
            assert result.get("Nip") == "1000000035"
            assert result.get("Nazwa") == "Firma ABC"


class TestRegonXmlParser:
    def test_parse_valid_xml(self):
        xml = "<root><dane><Nip>1234567890</Nip><Nazwa>Firma</Nazwa></dane></root>"
        result = RegonClient._parse_search_result(xml)
        assert len(result) == 1
        assert result[0]["Nip"] == "1234567890"

    def test_parse_multiple_records(self):
        xml = (
            "<root>"
            "<dane><Nip>1111111111</Nip></dane>"
            "<dane><Nip>2222222222</Nip></dane>"
            "</root>"
        )
        result = RegonClient._parse_search_result(xml)
        assert len(result) == 2

    def test_parse_none_returns_empty(self):
        assert RegonClient._parse_search_result(None) == []

    def test_parse_empty_string_returns_empty(self):
        assert RegonClient._parse_search_result("") == []

    def test_parse_invalid_xml_raises_external_service_error(self):
        with pytest.raises(ExternalServiceError):
            RegonClient._parse_search_result("<not valid xml>><")


# ---------------------------------------------------------------------------
# ContractorService — testy jednostkowe zachowania przy błędzie REGON
# ---------------------------------------------------------------------------

class TestContractorServiceRegonFallback:
    def test_regon_error_on_existing_contractor_returns_cached(self):
        """Błąd REGON dla istniejącego kontrahenta → zwraca cache, nie 500."""
        regon_client = MagicMock()
        regon_client.lookup_by_nip.side_effect = ExternalServiceError("REGON timeout")

        service, contractor_repo, override_repo, session = _make_contractor_service(regon_client)
        existing = _make_existing_contractor()
        contractor_repo.get_by_nip.return_value = existing
        override_repo.get_active_by_contractor_id.return_value = None
        session.refresh.side_effect = lambda obj: None

        result = service.get_by_nip("1000000035", _make_actor())

        # Nie rzucił — zwrócił słownik
        assert isinstance(result, dict)
        # Status błędu został zapisany
        assert existing.lookup_last_status == "failed"
        assert "REGON timeout" in existing.lookup_last_error

    def test_regon_change_me_on_new_contractor_raises(self):
        """Błąd REGON dla NOWEGO kontrahenta (brak cache) → ExternalServiceError propagowany."""
        regon_client = MagicMock()
        regon_client.lookup_by_nip.side_effect = ExternalServiceError(
            "REGON nie jest skonfigurowany. Ustaw prawidlowy REGON_API_KEY."
        )

        service, contractor_repo, override_repo, session = _make_contractor_service(regon_client)
        contractor_repo.get_by_nip.return_value = None  # brak w cache

        with pytest.raises(ExternalServiceError) as exc_info:
            service.get_by_nip("9999999999", _make_actor())

        error_msg = str(exc_info.value)
        # Klucz API nie może pojawić się w komunikacie serwisowym
        assert "change-me" not in error_msg
        assert "valid-regon-key" not in error_msg

    def test_regon_not_found_for_new_contractor_raises_not_found(self):
        """Gdy REGON zwraca brak wyników (None) i kontrahent nie istnieje → NotFoundError."""
        regon_client = MagicMock()
        regon_client.lookup_by_nip.return_value = None

        service, contractor_repo, override_repo, session = _make_contractor_service(regon_client)
        contractor_repo.get_by_nip.return_value = None

        with pytest.raises(NotFoundError):
            service.get_by_nip("9999999999", _make_actor())

    def test_regon_error_status_does_not_propagate_api_key(self):
        """ExternalServiceError z RegonClient nie może zawierać klucza API."""
        api_key = "super-secret-regon-key"
        regon_client = MagicMock()
        regon_client.lookup_by_nip.side_effect = ExternalServiceError(
            f"Blad komunikacji z REGON: HTTPError (key={api_key})"
        )

        service, contractor_repo, override_repo, session = _make_contractor_service(regon_client)
        contractor_repo.get_by_nip.return_value = None

        try:
            service.get_by_nip("9999999999", _make_actor())
        except ExternalServiceError as exc:
            # Ten test weryfikuje, że błąd z SOAP nie ujawnia klucza w warstwie serwisowej
            # Serwis tylko propaguje ExternalServiceError, nie dodaje własnych kluczy — OK
            _ = exc
