#!/usr/bin/env python3
"""PoC diagnostyczny: POST /invoices/query/metadata (KSeF API v2).

Nie modyfikuje sync zakupów IFG. Używa istniejącego KSeFAuthProvider lub aktywnej sesji z DB.

Przykład:
    python scripts/ksef_metadata_probe.py \\
        --date-from 2026-03-01 --date-to 2026-06-09 \\
        --subject all --date-type all

    python scripts/ksef_metadata_probe.py --auth session --nip 9670402857 \\
        --subject Subject2 --date-type PermanentStorage \\
        --date-from 2026-03-01 --date-to 2026-06-09
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.integrations.ksef.auth import KSeFAuthError, KSeFAuthProvider
from app.persistence.db import session_scope
from app.persistence.models.ksef_session import KSeFSessionORM

_KSEF_URLS = {
    "test": "https://api-test.ksef.mf.gov.pl/v2",
    "production": "https://api.ksef.mf.gov.pl/v2",
}

SUBJECT_CHOICES = ("Subject1", "Subject2", "Subject3")
DATE_TYPE_CHOICES = ("Issue", "Invoicing", "PermanentStorage")
KSEF_NUMBER_KEYS = ("ksefNumber", "ksefReferenceNumber", "ksef_reference_number")

# Klucz używany przez KSeFSessionService / KSeFClient w normalnym syncu.
_SYNC_ACCESS_TOKEN_KEY = "access_token"
_TOKEN_LIKE_METADATA_KEYS = (
    "access_token",
    "refresh_token",
    "session_token",
    "bearer",
    "token",
)


@dataclass(frozen=True)
class ResolvedAuth:
    access_token: str
    auth_mode: str
    token_source: str
    session_reference: str | None = None
    db_session_id: str | None = None
    metadata_keys_present: tuple[str, ...] = ()


def _parse_date_arg(value: str, *, end_of_day: bool = False) -> str:
    parsed = date.fromisoformat(value)
    if end_of_day:
        dt = datetime.combine(parsed, time(23, 59, 59), tzinfo=timezone.utc)
    else:
        dt = datetime.combine(parsed, time(0, 0, 0), tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _token_sha256_prefix(token: str, *, length: int = 12) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:length]


def _token_like_keys_present(metadata: dict) -> tuple[str, ...]:
    return tuple(key for key in _TOKEN_LIKE_METADATA_KEYS if metadata.get(key))


def _log_token_diagnostics(resolved: ResolvedAuth) -> None:
    token = resolved.access_token
    print(
        f"[auth-diag] source={resolved.auth_mode} "
        f"token_field={resolved.token_source} "
        f"length={len(token)} "
        f"sha256_prefix={_token_sha256_prefix(token)}"
    )
    if resolved.auth_mode == "session":
        print(f"[auth-diag] session_id={resolved.db_session_id or 'brak'}")
        print(f"[auth-diag] session_reference={resolved.session_reference or 'brak'}")
        keys = resolved.metadata_keys_present or ()
        print(
            "[auth-diag] token_metadata_json token-like keys: "
            f"{', '.join(keys) if keys else 'brak'}"
        )


def _resolve_access_token(*, auth: str, nip: str, access_token: str | None, env: str) -> ResolvedAuth:
    if auth == "token":
        if not access_token:
            raise SystemExit("--access-token wymagany przy --auth token")
        return ResolvedAuth(
            access_token=access_token,
            auth_mode="token",
            token_source="--access-token",
        )

    if auth == "session":
        with session_scope() as db:
            stmt = (
                select(KSeFSessionORM)
                .where(KSeFSessionORM.nip == nip, KSeFSessionORM.status == "active")
                .order_by(KSeFSessionORM.updated_at.desc())
            )
            orm = db.execute(stmt).scalars().first()
            if orm is None:
                raise SystemExit(f"Brak aktywnej sesji KSeF dla NIP={nip}")
            metadata = orm.token_metadata_json or {}
            keys_present = _token_like_keys_present(metadata)
            token = metadata.get(_SYNC_ACCESS_TOKEN_KEY)
            if not token:
                raise SystemExit(
                    f"Aktywna sesja nie zawiera {_SYNC_ACCESS_TOKEN_KEY!r} w token_metadata_json "
                    f"(obecne klucze token-like: {', '.join(keys_present) or 'brak'})"
                )
            print(
                f"[auth] Użyto {_SYNC_ACCESS_TOKEN_KEY!r} z token_metadata_json "
                f"(to samo pole co KSeFClient/sync; id={orm.id})"
            )
            return ResolvedAuth(
                access_token=token,
                auth_mode="session",
                token_source=f"token_metadata_json.{_SYNC_ACCESS_TOKEN_KEY}",
                session_reference=orm.session_reference,
                db_session_id=str(orm.id),
                metadata_keys_present=keys_present,
            )

    ksef_token = settings.ksef_auth_token
    if not ksef_token:
        raise SystemExit("Brak KSEF_AUTH_TOKEN w konfiguracji (.env)")
    provider = KSeFAuthProvider(
        environment=env,
        timeout_seconds=settings.ksef_timeout_seconds,
        auth_redeem_timeout_seconds=settings.ksef_auth_redeem_timeout_seconds,
    )
    try:
        session = provider.get_tokens(nip=nip, ksef_auth_token=ksef_token)
    except KSeFAuthError as exc:
        raise SystemExit(f"Błąd uwierzytelnienia KSeF: {exc}") from exc
    print(f"[auth] Nowy access_token z KSeFAuthProvider (env={env}, nip={nip})")
    return ResolvedAuth(
        access_token=session.access_token,
        auth_mode="fresh",
        token_source="KSeFAuthProvider.access_token",
    )


def _run_session_auth_check(
    *,
    base_url: str,
    access_token: str,
    session_reference: str,
    date_from: str,
    date_to: str,
    timeout: int,
) -> None:
    session_url = f"{base_url}/sessions/{session_reference}/invoices"
    params = {
        "invoiceType": "received",
        "subjectType": "subject2",
        "invoicingDateFrom": date_from,
        "invoicingDateTo": date_to,
    }
    print(f"[auth-check] GET {session_url} params={params}")
    try:
        resp = httpx.get(
            session_url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=timeout,
        )
        print(f"[auth-check] status={resp.status_code}")
        print(f"[auth-check] body_snippet={resp.text[:300]}")
    except Exception as exc:  # noqa: BLE001
        print("[auth-check] status=error")
        print(f"[auth-check] body_snippet={str(exc)[:300]}")


def _extract_invoices(payload: dict) -> list[dict]:
    for key in ("invoices", "invoiceList", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _extract_ksef_numbers(invoices: list[dict]) -> list[str]:
    numbers: list[str] = []
    for item in invoices:
        for key in KSEF_NUMBER_KEYS:
            ref = item.get(key)
            if isinstance(ref, str) and ref:
                numbers.append(ref)
                break
    return numbers


def _extract_total_count(payload: dict, invoices: list[dict]) -> int:
    for key in ("totalCount", "numberOfElements", "count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return len(invoices)


def query_invoice_metadata(
    *,
    base_url: str,
    access_token: str,
    subject_type: str,
    date_type: str,
    date_from: str,
    date_to: str,
    page_offset: int,
    page_size: int,
    timeout: int,
) -> dict:
    url = f"{base_url}/invoices/query/metadata"
    params = {"pageOffset": page_offset, "pageSize": page_size}
    body = {
        "subjectType": subject_type,
        "dateRange": {
            "dateType": date_type,
            "from": date_from,
            "to": date_to,
        },
    }
    print(f"[query] POST {url} subjectType={subject_type} dateType={date_type}")
    print(f"[query] dateRange={date_from} .. {date_to} pageOffset={page_offset} pageSize={page_size}")
    resp = httpx.post(
        url,
        params=params,
        json=body,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        snippet = resp.text[:500]
        raise RuntimeError(f"HTTP {resp.status_code}: {snippet}")
    return resp.json()


def _save_response(
    output_dir: Path,
    *,
    subject_type: str,
    date_type: str,
    payload: dict,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"ksef_metadata_{subject_type}_{date_type}_{ts}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _run_probe(
    *,
    base_url: str,
    access_token: str,
    subject_type: str,
    date_type: str,
    date_from: str,
    date_to: str,
    page_offset: int,
    page_size: int,
    timeout: int,
    output_dir: Path,
) -> int:
    try:
        payload = query_invoice_metadata(
            base_url=base_url,
            access_token=access_token,
            subject_type=subject_type,
            date_type=date_type,
            date_from=date_from,
            date_to=date_to,
            page_offset=page_offset,
            page_size=page_size,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[error] subjectType={subject_type} dateType={date_type}: {exc}")
        return 1

    invoices = _extract_invoices(payload)
    total = _extract_total_count(payload, invoices)
    numbers = _extract_ksef_numbers(invoices)
    out_path = _save_response(
        output_dir,
        subject_type=subject_type,
        date_type=date_type,
        payload=payload,
    )

    print(f"[result] subjectType={subject_type} dateType={date_type} total={total}")
    print(f"[result] first_ksef_numbers ({min(5, len(numbers))}): {numbers[:5]}")
    print(f"[result] response saved: {out_path}")
    return 0


def _expand_choice(value: str, choices: tuple[str, ...]) -> list[str]:
    if value.lower() == "all":
        return list(choices)
    if value not in choices:
        raise SystemExit(f"Nieobsługiwana wartość '{value}'. Dozwolone: {choices} lub 'all'")
    return [value]


def main() -> None:
    parser = argparse.ArgumentParser(description="KSeF v2 metadata probe (POST /invoices/query/metadata)")
    parser.add_argument("--env", choices=("test", "production"), default=None)
    parser.add_argument("--nip", default=None, help="NIP (domyślnie settings.seller_nip)")
    parser.add_argument(
        "--auth",
        choices=("fresh", "session", "token"),
        default="fresh",
        help="fresh=KSeFAuthProvider, session=aktywna sesja DB, token=--access-token",
    )
    parser.add_argument("--access-token", default=None, help="Bearer token (przy --auth token)")
    parser.add_argument("--subject", default="Subject2", help="Subject1|Subject2|Subject3|all")
    parser.add_argument("--date-type", default="PermanentStorage", help="Issue|Invoicing|PermanentStorage|all")
    parser.add_argument("--date-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--page-offset",
        type=int,
        default=0,
        help="Numer strony wyników (0, 1, 2…), nie offset rekordów",
    )
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "logs" / "ksef_metadata_probe"),
        help="Katalog na pełne odpowiedzi JSON",
    )
    args = parser.parse_args()

    env = args.env or settings.ksef_environment
    nip = (args.nip or settings.seller_nip or "").strip()
    if not nip:
        raise SystemExit("Podaj --nip lub ustaw SELLER_NIP w .env")

    base_url = _KSEF_URLS.get(env, _KSEF_URLS["test"])
    date_from = _parse_date_arg(args.date_from, end_of_day=False)
    date_to = _parse_date_arg(args.date_to, end_of_day=True)
    output_dir = Path(args.output_dir)

    resolved = _resolve_access_token(
        auth=args.auth,
        nip=nip,
        access_token=args.access_token,
        env=env,
    )
    _log_token_diagnostics(resolved)

    subjects = _expand_choice(args.subject, SUBJECT_CHOICES)
    date_types = _expand_choice(args.date_type, DATE_TYPE_CHOICES)

    print(f"[config] env={env} base_url={base_url} nip={nip} auth={args.auth}")
    print(f"[config] combinations={len(subjects) * len(date_types)}")

    if args.auth == "session":
        if not resolved.session_reference:
            print("[auth-check] session probe skipped (brak session_reference w DB)")
        else:
            _run_session_auth_check(
                base_url=base_url,
                access_token=resolved.access_token,
                session_reference=resolved.session_reference,
                date_from=date_from,
                date_to=date_to,
                timeout=args.timeout,
            )

    exit_code = 0
    for subject_type in subjects:
        for date_type in date_types:
            rc = _run_probe(
                base_url=base_url,
                access_token=resolved.access_token,
                subject_type=subject_type,
                date_type=date_type,
                date_from=date_from,
                date_to=date_to,
                page_offset=args.page_offset,
                page_size=args.page_size,
                timeout=args.timeout,
                output_dir=output_dir,
            )
            exit_code = max(exit_code, rc)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
