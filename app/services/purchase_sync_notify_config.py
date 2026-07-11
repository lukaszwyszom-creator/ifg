"""Pomocnicze funkcje konfiguracji powiadomień e-mail sync zakupów KSeF."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Sekundy do następnej próby po nieudanej próbie N (indeks = attempt_count po fail).
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (
    0,
    5 * 60,
    15 * 60,
    30 * 60,
    60 * 60,
)


def parse_notify_recipients(
    *,
    recipients_csv: str | None,
    legacy_email: str | None,
) -> list[str]:
    """Parsuje CSV odbiorców z fallbackiem do starej zmiennej."""
    raw = (recipients_csv or "").strip()
    if not raw:
        raw = (legacy_email or "").strip()
    if not raw:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for part in raw.split(","):
        addr = part.strip()
        if not addr or "@" not in addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(addr)
    return result


def compute_next_attempt_at(*, attempt_count: int, now: datetime | None = None) -> datetime | None:
    """Zwraca czas następnej próby lub None gdy limit wyczerpany."""
    if attempt_count >= len(RETRY_BACKOFF_SECONDS):
        return None
    delay = RETRY_BACKOFF_SECONDS[attempt_count]
    base = now or datetime.now(UTC)
    if delay <= 0:
        return base
    return base + timedelta(seconds=delay)


def retry_delay_seconds(attempt_count: int) -> int:
    """Opóźnienie przed kolejną próbą po attempt_count nieudanych próbach."""
    if attempt_count < 0 or attempt_count >= len(RETRY_BACKOFF_SECONDS):
        return 0
    return RETRY_BACKOFF_SECONDS[attempt_count]


def infer_session_slot_label(finished_at: datetime | None) -> str | None:
    """Rozpoznaje slot 08:00 / 14:00 na podstawie czasu zakończenia (Europe/Warsaw)."""
    if finished_at is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        local = finished_at.astimezone(ZoneInfo("Europe/Warsaw"))
    except Exception:
        local = finished_at.astimezone()
    hour = local.hour
    minute = local.minute
    if hour == 8 and minute < 30:
        return "08:00"
    if hour == 14 and minute < 30:
        return "14:00"
    return None
