from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

from app.persistence.models.ksef_session import KSeFSessionORM

# Statusy sesji / uwierzytelnienia KSeF w DB
SESSION_ACTIVE = "active"  # sesja online (wysyłka sprzedaży)
SESSION_AUTH_ACTIVE = "auth_active"  # wyłącznie tokeny zakupów (bez sesji online)
SESSION_TERMINATED = "terminated"
SESSION_EXPIRED = "expired"
SESSION_FAILED = "failed"

TOKEN_CACHE_MARGIN = timedelta(seconds=30)

KEY_ACCESS_TOKEN = "access_token"
KEY_REFRESH_TOKEN = "refresh_token"
KEY_REFRESH_VALID = "refresh_valid_until"
KEY_SYMMETRIC_KEY = "symmetric_key"
KEY_IV = "initialization_vector"


def normalize_session_nip(nip: str | None) -> str:
    raw = (nip or "").strip().upper()
    if raw.startswith("PL"):
        raw = raw[2:].strip()
    return raw.replace("-", "").replace(" ", "")


def as_utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def access_token_valid(orm: KSeFSessionORM, *, margin: timedelta = TOKEN_CACHE_MARGIN) -> bool:
    metadata = orm.token_metadata_json or {}
    if not metadata.get(KEY_ACCESS_TOKEN):
        return False
    expires_at = as_utc_aware(orm.expires_at)
    if expires_at is None:
        return True
    return datetime.now(UTC) < expires_at - margin


def refresh_token_valid(orm: KSeFSessionORM) -> bool:
    metadata = orm.token_metadata_json or {}
    refresh = metadata.get(KEY_REFRESH_TOKEN)
    if not refresh:
        return False
    raw_valid = metadata.get(KEY_REFRESH_VALID)
    if not raw_valid:
        return True
    try:
        refresh_until = datetime.fromisoformat(str(raw_valid).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True
    return datetime.now(UTC) < as_utc_aware(refresh_until)  # type: ignore[arg-type]


def is_online_session(orm: KSeFSessionORM) -> bool:
    return bool((orm.session_reference or "").strip())


def build_token_metadata(
    *,
    access_token: str,
    refresh_token: str,
    refresh_valid_until: datetime | None,
    symmetric_key: bytes | None = None,
    initialization_vector: bytes | None = None,
    existing: dict | None = None,
) -> dict:
    metadata = dict(existing or {})
    metadata[KEY_ACCESS_TOKEN] = access_token
    metadata[KEY_REFRESH_TOKEN] = refresh_token
    if refresh_valid_until is not None:
        metadata[KEY_REFRESH_VALID] = refresh_valid_until.isoformat()
    elif existing is None:
        metadata[KEY_REFRESH_VALID] = None
    if symmetric_key is not None:
        metadata[KEY_SYMMETRIC_KEY] = base64.b64encode(symmetric_key).decode("ascii")
    if initialization_vector is not None:
        metadata[KEY_IV] = base64.b64encode(initialization_vector).decode("ascii")
    return metadata
