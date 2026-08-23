"""Diagnostyka połączenia SMTP bez wysyłki wiadomości."""
from __future__ import annotations

import socket
import smtplib

from ifg_guardian.plugins.ifg.smtp.models import ConnectivityCheck, SmtpStageStatus


def _smtp_text(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_connectivity_checks(config) -> list[ConnectivityCheck]:
    checks: list[ConnectivityCheck] = []
    host = config.host
    port = config.port

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addrs = sorted({item[4][0] for item in infos})
        checks.append(
            ConnectivityCheck(
                "DNS",
                SmtpStageStatus.PASS,
                f"resolved {host} → {', '.join(addrs[:3])}",
            )
        )
    except OSError as exc:
        checks.append(ConnectivityCheck("DNS", SmtpStageStatus.FAIL, str(exc)))
        return checks

    smtp: smtplib.SMTP | None = None
    try:
        smtp = smtplib.SMTP(host, port, timeout=30)
        checks.append(
            ConnectivityCheck("TCP", SmtpStageStatus.PASS, f"connected {host}:{port}")
        )
    except OSError as exc:
        checks.append(ConnectivityCheck("TCP", SmtpStageStatus.FAIL, str(exc)))
        return checks

    try:
        code, greeting = smtp.ehlo()
        greeting_text = _smtp_text(greeting)[:120]
        if 200 <= code < 300:
            checks.append(ConnectivityCheck("HELO/EHLO", SmtpStageStatus.PASS, greeting_text))
        else:
            checks.append(ConnectivityCheck("HELO/EHLO", SmtpStageStatus.FAIL, f"code={code} {greeting_text[:80]}"))

        if config.use_tls:
            try:
                smtp.starttls()
                smtp.ehlo()
                checks.append(ConnectivityCheck("STARTTLS", SmtpStageStatus.PASS, "TLS negotiated"))
            except smtplib.SMTPException as exc:
                checks.append(ConnectivityCheck("STARTTLS", SmtpStageStatus.FAIL, str(exc)))
                return checks
        else:
            checks.append(ConnectivityCheck("STARTTLS", SmtpStageStatus.WARN, "disabled (SMTP_USE_TLS=false)"))

        if config.user and config.password:
            try:
                smtp.login(config.user, config.password)
                checks.append(ConnectivityCheck("AUTH", SmtpStageStatus.PASS, "login accepted"))
            except smtplib.SMTPException as exc:
                checks.append(ConnectivityCheck("AUTH", SmtpStageStatus.FAIL, str(exc)))
        else:
            checks.append(ConnectivityCheck("AUTH", SmtpStageStatus.WARN, "skipped — no credentials"))
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except smtplib.SMTPException:
                pass

    return checks
