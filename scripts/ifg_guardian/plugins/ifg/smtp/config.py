"""Odczyt i walidacja konfiguracji SMTP dla Guardiana."""
from __future__ import annotations

import sys
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.plugins.ifg.smtp.models import ConfigCheck, SmtpStageStatus


SMTP_CONFIG_KEYS: tuple[str, ...] = (
    "PURCHASE_SYNC_NOTIFY_ENABLED",
    "PURCHASE_SYNC_NOTIFY_RECIPIENTS",
    "PURCHASE_SYNC_NOTIFY_EMAIL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "SMTP_USE_TLS",
    "APP_VERSION",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_env_text(path.read_text(encoding="utf-8"))


def parse_env_text(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_local_env_path(*, env_file: Path | None = None) -> Path:
    if env_file is not None:
        return env_file
    candidates = [
        ROOT / ".env.production",
        ROOT / ".env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return ROOT / ".env.production"


def load_smtp_env(*, env_file: Path | None = None) -> tuple[dict[str, str], str]:
    """Load SMTP env from local filesystem (legacy helper)."""
    return load_smtp_env_local(env_file=env_file)


def load_smtp_env_local(*, env_file: Path | None = None) -> tuple[dict[str, str], str]:
    if env_file is not None:
        if env_file.is_file():
            return _parse_env_file(env_file), str(env_file.resolve())
        return {}, str(env_file.resolve())
    path = resolve_local_env_path(env_file=None)
    if path.is_file():
        return _parse_env_file(path), str(path.resolve())
    return {}, str(path.resolve())


def mask_email(value: str) -> str:
    text = (value or "").strip()
    if not text or "@" not in text:
        return "(empty)"
    local, domain = text.split("@", 1)
    if len(local) <= 2:
        masked_local = f"{local[:1]}***"
    else:
        masked_local = f"{local[:2]}***"
    return f"{masked_local}@{domain}"


def mask_secret(value: str | None, *, present_label: str = "(set)") -> str:
    if value and value.strip():
        return present_label
    return "(missing)"


def mask_config_values(values: dict[str, str]) -> dict[str, str]:
    return {
        "PURCHASE_SYNC_NOTIFY_ENABLED": values.get("PURCHASE_SYNC_NOTIFY_ENABLED", "") or "(missing)",
        "PURCHASE_SYNC_NOTIFY_RECIPIENTS": _mask_recipients_csv(values.get("PURCHASE_SYNC_NOTIFY_RECIPIENTS", "")),
        "PURCHASE_SYNC_NOTIFY_EMAIL": mask_email(values.get("PURCHASE_SYNC_NOTIFY_EMAIL", "")),
        "SMTP_HOST": values.get("SMTP_HOST", "") or "(missing)",
        "SMTP_PORT": values.get("SMTP_PORT", "") or "(missing)",
        "SMTP_USER": mask_email(values.get("SMTP_USER", "")) if values.get("SMTP_USER") else "(missing)",
        "SMTP_PASSWORD": mask_secret(values.get("SMTP_PASSWORD")),
        "SMTP_FROM": mask_email(values.get("SMTP_FROM", "")) if values.get("SMTP_FROM") else "(missing)",
        "SMTP_USE_TLS": values.get("SMTP_USE_TLS", "") or "(missing)",
    }


def _mask_recipients_csv(raw: str) -> str:
    if not raw.strip():
        return "(empty)"
    parts = [mask_email(part.strip()) for part in raw.split(",") if part.strip()]
    return ", ".join(parts) if parts else "(empty)"


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _parse_port(value: str | None) -> int:
    try:
        return int(str(value or "587").strip())
    except ValueError:
        return 587


def parse_notify_recipients(values: dict[str, str]) -> list[str]:
    _ensure_app_importable()
    from app.services.purchase_sync_notify_config import parse_notify_recipients as app_parse

    return app_parse(
        recipients_csv=values.get("PURCHASE_SYNC_NOTIFY_RECIPIENTS"),
        legacy_email=values.get("PURCHASE_SYNC_NOTIFY_EMAIL"),
    )


def build_smtp_config(values: dict[str, str]):
    _ensure_app_importable()
    from app.integrations.email.smtp_client import SmtpConfig

    host = (values.get("SMTP_HOST") or "").strip()
    if not host:
        return None
    from_addr = (values.get("SMTP_FROM") or "").strip()
    if not from_addr:
        return None
    try:
        from app.integrations.email.smtp_client import parse_smtp_from

        _, envelope = parse_smtp_from(from_addr)
    except Exception:
        return None
    user = (values.get("SMTP_USER") or "").strip() or None
    password = values.get("SMTP_PASSWORD") or None
    if password is not None:
        password = password.strip() or None
    return SmtpConfig(
        host=host,
        port=_parse_port(values.get("SMTP_PORT")),
        user=user,
        password=password,
        from_addr=from_addr,
        use_tls=_parse_bool(values.get("SMTP_USE_TLS", "true")),
    )


def run_config_checks(values: dict[str, str]) -> tuple[list[ConfigCheck], list[str], bool]:
    checks: list[ConfigCheck] = []
    notify_enabled = _parse_bool(values.get("PURCHASE_SYNC_NOTIFY_ENABLED"))
    recipients = parse_notify_recipients(values)

    def add(key: str, status: SmtpStageStatus, message: str, masked: str = "") -> None:
        checks.append(ConfigCheck(key=key, status=status, message=message, masked_value=masked))

    masked = mask_config_values(values)

    add(
        "PURCHASE_SYNC_NOTIFY_ENABLED",
        SmtpStageStatus.PASS if values.get("PURCHASE_SYNC_NOTIFY_ENABLED") is not None else SmtpStageStatus.WARN,
        "enabled" if notify_enabled else "disabled",
        masked["PURCHASE_SYNC_NOTIFY_ENABLED"],
    )

    host = (values.get("SMTP_HOST") or "").strip()
    if not host:
        add("SMTP_HOST", SmtpStageStatus.FAIL, "SMTP_HOST is required", masked["SMTP_HOST"])
    else:
        add("SMTP_HOST", SmtpStageStatus.PASS, host, masked["SMTP_HOST"])

    port_raw = (values.get("SMTP_PORT") or "").strip()
    if not port_raw:
        add("SMTP_PORT", SmtpStageStatus.WARN, "default 587", "587")
    else:
        add("SMTP_PORT", SmtpStageStatus.PASS, port_raw, masked["SMTP_PORT"])

    from_addr = (values.get("SMTP_FROM") or "").strip()
    if not from_addr:
        add("SMTP_FROM", SmtpStageStatus.FAIL, "SMTP_FROM is required", masked["SMTP_FROM"])
    else:
        try:
            _ensure_app_importable()
            from app.integrations.email.smtp_client import SmtpFromParseError, parse_smtp_from

            _, envelope = parse_smtp_from(from_addr)
            add(
                "SMTP_FROM",
                SmtpStageStatus.PASS,
                f"envelope sender: {mask_email(envelope)}",
                masked["SMTP_FROM"],
            )
        except SmtpFromParseError as exc:
            add("SMTP_FROM", SmtpStageStatus.FAIL, str(exc), masked["SMTP_FROM"])
        except Exception as exc:
            add("SMTP_FROM", SmtpStageStatus.FAIL, f"invalid SMTP_FROM: {exc}", masked["SMTP_FROM"])

    user = (values.get("SMTP_USER") or "").strip()
    password = (values.get("SMTP_PASSWORD") or "").strip()
    if user and not password:
        add("SMTP_PASSWORD", SmtpStageStatus.FAIL, "SMTP_PASSWORD required when SMTP_USER is set", masked["SMTP_PASSWORD"])
    elif password:
        add("SMTP_PASSWORD", SmtpStageStatus.PASS, masked["SMTP_PASSWORD"], masked["SMTP_PASSWORD"])
    else:
        add("SMTP_PASSWORD", SmtpStageStatus.WARN, "no SMTP auth configured", masked["SMTP_PASSWORD"])

    if user:
        add("SMTP_USER", SmtpStageStatus.PASS, mask_email(user), masked["SMTP_USER"])
    else:
        add("SMTP_USER", SmtpStageStatus.WARN, "optional — anonymous SMTP", masked["SMTP_USER"])

    tls_raw = values.get("SMTP_USE_TLS")
    if tls_raw is None or not str(tls_raw).strip():
        add("SMTP_USE_TLS", SmtpStageStatus.WARN, "default true", "true")
    else:
        add("SMTP_USE_TLS", SmtpStageStatus.PASS, str(tls_raw).strip(), masked["SMTP_USE_TLS"])

    recipients_csv = (values.get("PURCHASE_SYNC_NOTIFY_RECIPIENTS") or "").strip()
    legacy_email = (values.get("PURCHASE_SYNC_NOTIFY_EMAIL") or "").strip()
    if recipients_csv:
        add(
            "PURCHASE_SYNC_NOTIFY_RECIPIENTS",
            SmtpStageStatus.PASS,
            f"{len(recipients)} recipient(s) after CSV parse",
            masked["PURCHASE_SYNC_NOTIFY_RECIPIENTS"],
        )
    elif legacy_email:
        add(
            "PURCHASE_SYNC_NOTIFY_RECIPIENTS",
            SmtpStageStatus.WARN,
            "using deprecated PURCHASE_SYNC_NOTIFY_EMAIL fallback",
            masked["PURCHASE_SYNC_NOTIFY_EMAIL"],
        )
    else:
        status = SmtpStageStatus.FAIL if notify_enabled else SmtpStageStatus.WARN
        add(
            "PURCHASE_SYNC_NOTIFY_RECIPIENTS",
            status,
            "no recipients configured",
            masked["PURCHASE_SYNC_NOTIFY_RECIPIENTS"],
        )

    if legacy_email:
        add(
            "PURCHASE_SYNC_NOTIFY_EMAIL",
            SmtpStageStatus.WARN,
            "deprecated fallback configured",
            masked["PURCHASE_SYNC_NOTIFY_EMAIL"],
        )
    else:
        add("PURCHASE_SYNC_NOTIFY_EMAIL", SmtpStageStatus.PASS, "not used", masked["PURCHASE_SYNC_NOTIFY_EMAIL"])

    if notify_enabled and not recipients:
        add(
            "recipients.validation",
            SmtpStageStatus.FAIL,
            "notify enabled but no valid recipients",
        )
    elif recipients:
        add(
            "recipients.validation",
            SmtpStageStatus.PASS,
            f"{len(recipients)} unique recipient(s), no empty addresses",
        )
    else:
        add("recipients.validation", SmtpStageStatus.WARN, "notify disabled — recipients not required")

    raw_parts = [p.strip() for p in recipients_csv.split(",") if recipients_csv]
    if raw_parts:
        invalid = [p for p in raw_parts if "@" not in p]
        if invalid:
            add("recipients.csv", SmtpStageStatus.WARN, f"skipped {len(invalid)} invalid address(es)")
        else:
            add("recipients.csv", SmtpStageStatus.PASS, "CSV parser OK")

    if recipients_csv and len(recipients) < len([p for p in raw_parts if "@" in p]):
        add("recipients.dedup", SmtpStageStatus.PASS, "duplicates removed (case-insensitive)")

    return checks, recipients, notify_enabled


def _ensure_app_importable() -> None:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
