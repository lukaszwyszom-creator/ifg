from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from zeep import Client
from zeep.transports import Transport

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class RegonClient:
    def __init__(
        self,
        api_key: str | None,
        environment: str,
        timeout_seconds: int,
        wsdl_test: str,
        wsdl_production: str,
    ) -> None:
        self.api_key = api_key
        self.environment = environment
        self.timeout_seconds = timeout_seconds
        self.wsdl_test = wsdl_test
        self.wsdl_production = wsdl_production

    def lookup_by_nip(self, nip: str) -> dict | None:
        if not self._is_api_key_configured():
            logger.error(
                "REGON lookup blocked: missing or placeholder REGON_API_KEY "
                "(environment=%s, wsdl=%s)",
                self.environment,
                self._resolve_wsdl(),
            )
            raise ExternalServiceError(
                "REGON nie jest skonfigurowany. Ustaw prawidlowy REGON_API_KEY."
            )

        wsdl_url = self._resolve_wsdl()
        logger.info(
            "REGON lookup start: environment=%s wsdl=%s nip=%s",
            self.environment,
            wsdl_url,
            nip,
        )

        session_id: str | None = None
        try:
            client = Client(wsdl=wsdl_url, transport=Transport(timeout=self.timeout_seconds))
        except Exception as exc:
            logger.error(
                "REGON WSDL load failed: environment=%s wsdl=%s error=%s",
                self.environment,
                wsdl_url,
                type(exc).__name__,
            )
            raise ExternalServiceError(f"Blad ladowania WSDL REGON: {type(exc).__name__}") from exc

        try:
            session_id = client.service.Zaloguj(self.api_key)
            if not session_id or not str(session_id).strip():
                logger.error(
                    "REGON login failed: environment=%s wsdl=%s empty_session_id=true",
                    self.environment,
                    wsdl_url,
                )
                raise ExternalServiceError(
                    "REGON odmowil logowania (pusty identyfikator sesji). "
                    "Sprawdz poprawnosc REGON_API_KEY."
                )

            logger.info(
                "REGON login ok: environment=%s wsdl=%s session_ok=true",
                self.environment,
                wsdl_url,
            )

            client.transport.session.headers.update({"sid": str(session_id)})
            result_xml = client.service.DaneSzukajPodmioty({"Nip": nip})
        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.error(
                "REGON SOAP error: environment=%s wsdl=%s nip=%s error=%s",
                self.environment,
                wsdl_url,
                nip,
                type(exc).__name__,
            )
            raise ExternalServiceError(f"Blad komunikacji z REGON: {exc}") from exc
        finally:
            try:
                if session_id:
                    client.transport.session.headers.update({"sid": str(session_id)})
                    client.service.Wyloguj(session_id)
            except Exception:
                pass

        records = self._parse_search_result(result_xml)
        logger.info(
            "REGON lookup finished: environment=%s nip=%s records=%d has_data=%s",
            self.environment,
            nip,
            len(records),
            bool(records),
        )
        if not records:
            return None
        return records[0]

    def _is_api_key_configured(self) -> bool:
        if not self.api_key:
            return False
        normalized = self.api_key.strip()
        return bool(normalized) and normalized.lower() != "change-me"

    def _resolve_wsdl(self) -> str:
        if self.environment == "test":
            return self.wsdl_test
        return self.wsdl_production

    @staticmethod
    def _local_tag(tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag

    @classmethod
    def _parse_search_result(cls, result_xml: str | None) -> list[dict]:
        if not result_xml:
            return []

        if not isinstance(result_xml, str):
            result_xml = str(result_xml).strip()
        if not result_xml:
            return []

        try:
            root = ET.fromstring(result_xml)
        except ET.ParseError as exc:
            raise ExternalServiceError("REGON zwrocil nieprawidlowy XML.") from exc

        records: list[dict] = []
        for node in root.iter():
            if cls._local_tag(node.tag) != "dane":
                continue

            record: dict[str, str] = {}
            for child in node:
                record[cls._local_tag(child.tag)] = child.text or ""

            if not record:
                continue

            if record.get("ErrorCode"):
                logger.info(
                    "REGON search returned error record: code=%s message=%s",
                    record.get("ErrorCode"),
                    record.get("ErrorMessagePl") or record.get("ErrorMessageEn"),
                )
                continue

            records.append(record)

        return records
