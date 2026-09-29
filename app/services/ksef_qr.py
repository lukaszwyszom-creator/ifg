"""KSeF verification QR (Kod I) — presentation helpers.

Builds the official invoice verification URL from the FA(3) XML bytes that were
actually submitted (stored on ``transmissions.xml_content``).

Does NOT invent hashes. Incomplete inputs → no QR.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

_NIP_RE = re.compile(r"^\d{10}$")

_QR_BASE_BY_ENV: dict[str, str] = {
    "test": "https://qr-test.ksef.mf.gov.pl",
    "demo": "https://qr-demo.ksef.mf.gov.pl",
    "prod": "https://qr.ksef.mf.gov.pl",
    "production": "https://qr.ksef.mf.gov.pl",
}


@dataclass(frozen=True)
class KSeFQrPayload:
    """Complete Kod I payload ready for QR encoding."""

    url: str
    nip: str
    issue_date: date
    hash_base64url: str


def normalize_ksef_qr_environment(raw: str | None) -> str:
    env = (raw or "test").strip().lower()
    if env in _QR_BASE_BY_ENV:
        return env
    return "test"


def qr_base_url(environment: str | None) -> str:
    env = normalize_ksef_qr_environment(environment)
    return _QR_BASE_BY_ENV[env]


def sha256_digest_base64url(xml_bytes: bytes) -> str:
    """Same digest family as KSeF ``invoiceHash``, encoded base64url (no padding)."""
    digest = hashlib.sha256(xml_bytes).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_invoice_verification_url(
    *,
    seller_nip: str,
    issue_date: date,
    xml_bytes: bytes,
    environment: str | None = None,
) -> KSeFQrPayload | None:
    """Return Kod I URL or None when required data is incomplete/invalid."""
    nip = (seller_nip or "").strip()
    if not _NIP_RE.match(nip):
        return None
    if issue_date is None:
        return None
    if not xml_bytes:
        return None
    hash_b64url = sha256_digest_base64url(xml_bytes)
    date_part = issue_date.strftime("%d-%m-%Y")
    url = f"{qr_base_url(environment)}/invoice/{nip}/{date_part}/{hash_b64url}"
    return KSeFQrPayload(
        url=url,
        nip=nip,
        issue_date=issue_date,
        hash_base64url=hash_b64url,
    )


def render_qr_png_data_uri(url: str, *, scale: int = 4) -> str | None:
    """Encode URL as PNG QR data-URI via ``segno`` (no network fetch)."""
    try:
        import segno
    except ImportError:
        logger.warning("segno not installed — cannot render KSeF QR")
        return None
    import io

    qr = segno.make(url, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=1)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def resolve_seller_nip_for_qr(seller_snapshot: dict | None) -> str:
    snap = seller_snapshot or {}
    raw = snap.get("nip") or snap.get("NIP") or ""
    digits = re.sub(r"\D", "", str(raw))
    return digits if _NIP_RE.match(digits) else ""


def resolve_submitted_fa3_xml(transmissions: list) -> bytes | None:
    """Pick durable FA(3) bytes from transmission rows (newest-first list).

    Prefer ``success`` with ``xml_content`` (exact bytes submitted to KSeF).
    Fallback: any row with non-empty ``xml_content``.
    """
    preferred: bytes | None = None
    fallback: bytes | None = None
    for tx in transmissions:
        raw = getattr(tx, "xml_content", None)
        if not raw:
            continue
        blob = bytes(raw)
        if not blob:
            continue
        status = (getattr(tx, "status", None) or "").strip().lower()
        if status == "success" and preferred is None:
            preferred = blob
        if fallback is None:
            fallback = blob
    return preferred or fallback
