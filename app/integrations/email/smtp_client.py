"""Prosty klient SMTP (stdlib) — bez sekretów w repo."""
from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


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

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.from_addr
    message["To"] = ", ".join(recipients)
    message.set_content(body_text)

    try:
        with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
            if config.use_tls:
                smtp.starttls()
            if config.user and config.password:
                smtp.login(config.user, config.password)
            smtp.send_message(message, to_addrs=recipients)
    except smtplib.SMTPException as exc:
        raise SmtpSendError(str(exc)) from exc
    except OSError as exc:
        raise SmtpSendError(str(exc)) from exc
