"""CSV parser dla importu wyciągów bankowych (PaymentService).

Wydzielone z ``payment_service`` w celu izolacji logiki I/O od logiki domenowej.
Logika nie została zmieniona — wyłącznie przeniesiona.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Nazwy kolumn CSV akceptowane przez importer (case-insensitive)
# ---------------------------------------------------------------------------
_CSV_COLUMN_ALIASES: dict[str, list[str]] = {
    "transaction_date": ["data", "data operacji", "transactiondate", "transaction_date", "data transakcji"],
    "value_date": ["data waluty", "valuedate", "value_date"],
    "amount": ["kwota", "amount", "wartość", "wartosc"],
    "currency": ["waluta", "currency"],
    "counterparty_name": ["nazwa kontrahenta", "counterparty", "counterparty_name", "odbiorca/nadawca"],
    "counterparty_account": ["nr konta kontrahenta", "counterparty_account", "konto kontrahenta"],
    "title": ["tytuł", "tytul", "title", "opis", "szczegoly", "szczegóły przelewu"],
    "external_id": ["id transakcji", "external_id", "reference", "numer transakcji"],
}


def _parse_csv(content: str) -> list[dict[str, str]]:
    """Parsuje CSV z automatycznym wykryciem separatora i mapowaniem kolumn."""
    # Wykryj separator
    sample = content[:2048]
    sep = ";" if sample.count(";") >= sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(content), delimiter=sep)
    if reader.fieldnames is None:
        return []

    col_map = _build_column_map(list(reader.fieldnames))
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        mapped: dict[str, str] = {}
        for canonical, aliases in _CSV_COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in col_map:
                    mapped[canonical] = (raw_row.get(col_map[alias]) or "").strip()
                    break
        if mapped:
            rows.append(mapped)
    return rows


def _build_column_map(fieldnames: list[str]) -> dict[str, str]:
    """Zwraca {lowercase_alias: original_fieldname}."""
    result: dict[str, str] = {}
    for name in fieldnames:
        if name:
            result[name.strip().lower()] = name
    return result


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Nierozpoznany format daty: {val!r}")
