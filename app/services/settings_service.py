from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.core.exceptions import ValidationError
from app.persistence.models.app_settings import AppSettingsORM
from app.persistence.repositories.app_settings_repository import AppSettingsRepository
from app.services.bank_account import validate_bank_account

_NIP_RE = re.compile(r"^\d{10}$")

# Pola które serwis obsługuje (guard przed przypadkowym nadpisaniem)
_ALLOWED_FIELDS = frozenset(
    {
        "seller_nip",
        "seller_name",
        "seller_street",
        "seller_building_no",
        "seller_apartment_no",
        "seller_postal_code",
        "seller_city",
        "seller_country",
        "seller_bank_account",
    }
)


class SettingsService:
    COMPANY_SETTINGS_MSG = "Uzupełnij dane sprzedawcy w Ustawieniach firmy."

    def __init__(self, session: Session, repository: AppSettingsRepository) -> None:
        self.session = session
        self.repository = repository

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        """Zwraca ustawienia: DB-first, fallback do zmiennych środowiskowych."""
        row = self.repository.get()
        return self._merge(row)

    def update_settings(self, data: dict) -> dict:
        """Waliduje i utrwala część ustawień w DB.

        Przyjmuje tylko pola z _ALLOWED_FIELDS — pozostałe są ignorowane.
        """
        filtered = {k: v for k, v in data.items() if k in _ALLOWED_FIELDS}
        if not filtered:
            raise ValidationError("Brak rozpoznanych pól do aktualizacji.")

        if "seller_nip" in filtered and filtered["seller_nip"] is not None:
            nip = filtered["seller_nip"]
            if not _NIP_RE.match(nip):
                raise ValidationError(
                    f"seller_nip musi składać się dokładnie z 10 cyfr, otrzymano: {nip!r}"
                )

        if "seller_bank_account" in filtered:
            try:
                filtered["seller_bank_account"] = validate_bank_account(
                    filtered["seller_bank_account"]
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        row = self.repository.upsert(filtered)
        return self._merge(row)

    def build_company_snapshot(self) -> dict:
        """Snapshot sprzedawcy do faktury sprzedaży (env + DB)."""
        merged = self.get_settings()
        return {
            "nip": str(merged.get("seller_nip") or "").strip(),
            "name": str(merged.get("seller_name") or "").strip(),
            "street": str(merged.get("seller_street") or "").strip(),
            "building_no": str(merged.get("seller_building_no") or "").strip(),
            "apartment_no": str(merged.get("seller_apartment_no") or "").strip(),
            "postal_code": str(merged.get("seller_postal_code") or "").strip(),
            "city": str(merged.get("seller_city") or "").strip(),
            "country": str(merged.get("seller_country") or "PL").strip() or "PL",
        }

    def validate_company_snapshot(self, snapshot: dict | None = None) -> None:
        """Waliduje kompletność danych sprzedawcy przed fakturą sprzedaży / wysyłką."""
        snap = snapshot if snapshot is not None else self.build_company_snapshot()
        name = str(snap.get("name") or "").strip()
        nip = str(snap.get("nip") or "").strip()
        street = str(snap.get("street") or "").strip()
        building_no = str(snap.get("building_no") or "").strip()
        postal_code = str(snap.get("postal_code") or "").strip()
        city = str(snap.get("city") or "").strip()
        country = str(snap.get("country") or "").strip()

        if not name or not nip:
            raise ValidationError(self.COMPANY_SETTINGS_MSG)
        if not country:
            raise ValidationError(self.COMPANY_SETTINGS_MSG)
        has_street_line = bool(street or building_no)
        has_locality = bool(city or postal_code)
        if not has_street_line or not has_locality:
            raise ValidationError(self.COMPANY_SETTINGS_MSG)

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    def _merge(self, row: AppSettingsORM | None) -> dict:
        """Scala ustawienia właściciela.

        Dane sprzedawcy są stałe dla tej instalacji, więc konfiguracja aplikacji
        jest źródłem prawdy. Wiersz DB zostaje tolerowany jako starszy fallback.
        """
        env = env_settings

        def fixed_or_db(env_val: str | None, db_val: str | None) -> str | None:
            if env_val is not None and str(env_val).strip():
                return str(env_val).strip()
            if db_val is not None:
                return str(db_val).strip()
            return None

        return {
            "seller_nip": fixed_or_db(
                env.seller_nip, row.seller_nip if row else None
            ),
            "seller_name": fixed_or_db(
                env.seller_name, row.seller_name if row else None
            ),
            "seller_street": fixed_or_db(
                env.seller_street, row.seller_street if row else None
            ),
            "seller_building_no": fixed_or_db(
                env.seller_building_no, row.seller_building_no if row else None
            ),
            "seller_apartment_no": fixed_or_db(
                env.seller_apartment_no, row.seller_apartment_no if row else None
            ),
            "seller_postal_code": fixed_or_db(
                env.seller_postal_code, row.seller_postal_code if row else None
            ),
            "seller_city": fixed_or_db(
                env.seller_city, row.seller_city if row else None
            ),
            "seller_country": fixed_or_db(env.seller_country or "PL", row.seller_country if row else None),
            "seller_bank_account": (
                str(row.seller_bank_account).strip()
                if row and row.seller_bank_account
                else None
            ),
            # źródło: tylko env (nie edytowalne przez API)
            "ksef_environment": env.ksef_environment,
            "app_env": env.app_env,
            "app_version": env.app_version,
        }
