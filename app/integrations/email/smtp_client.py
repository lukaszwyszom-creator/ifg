"""Prosty klient SMTP (stdlib) — bez sekretów w repo."""
from __future__ import annotations

import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, parseaddr


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str | None
    password: str | None
    from_addr: str
    use_tls: bool = True


class SmtpSendError(Exception):
    """Błąd wysyłki SMTP."""


class SmtpFromParseError(ValueError):
    """Niepoprawna wartość SMTP_FROM."""


_EMAIL_IN_ANGLE_RE = re.compile(r"^(.+?)\s*<([^<>@\s]+@[^<>@\s]+)>\s*$")
_SIMPLE_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def parse_smtp_from(raw: str) -> tuple[str, str]:
    """Parse SMTP_FROM into (From header, envelope sender).

    Examples:
        ds723@ikonastudio.pl -> (ds723@ikonastudio.pl, ds723@ikonastudio.pl)
        IFG [DS 723+] <ds723@ikonastudio.pl> -> ("IFG [DS 723+]" <ds723@...>, ds723@...)
    """
    value = (raw or "").strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    if not value:
        raise SmtpFromParseError("SMTP_FROM is empty")

    angle_match = _EMAIL_IN_ANGLE_RE.match(value)
    if angle_match:
        display = angle_match.group(1).strip().strip('"').strip("'")
        address = angle_match.group(2).strip()
        if not _SIMPLE_EMAIL_RE.match(address):
            raise SmtpFromParseError(f"SMTP_FROM has invalid address: {address!r}")
        header = formataddr((display, address)) if display else address
        return header, address

    display, address = parseaddr(value)
    address = (address or "").strip()
    if address and "@" in address and _SIMPLE_EMAIL_RE.match(address):
        header = formataddr((display, address)) if display else address
        return header, address

    if _SIMPLE_EMAIL_RE.match(value):
        return value, value

    raise SmtpFromParseError(
        "SMTP_FROM must be a valid e-mail address or 'Display Name <addr@domain>' "
        f"(got: {raw!r})"
    )


def send_email(
    *,
    config: SmtpConfig,
    to_addrs: str | list[str],
    subject: str,
    body_text: str,
) -> None:
    recipients = [to_addrs] if isinstance(to_addrs, str) else list(to_addrs)
    recipients = [addr.strip() for addr in recipients if addr and str(addr).strip()]
    if not recipients:
        raise SmtpSendError("Brak odbiorców e-mail.")

    try:
        from_header, envelope_from = parse_smtp_from(config.from_addr)
    except SmtpFromParseError as exc:
        raise SmtpSendError(str(exc)) from exc

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_header
    message["To"] = ", ".join(recipients)
    message.set_content(body_text)

    try:
        with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
            if config.use_tls:
                smtp.starttls()
            if config.user and config.password:
                smtp.login(config.user, config.password)
            smtp.send_message(message, from_addr=envelope_from, to_addrs=recipients)
    except smtplib.SMTPException as exc:
        raise SmtpSendError(str(exc)) from exc
    except OSError as exc:
        raise SmtpSendError(str(exc)) from exc
