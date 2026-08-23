"""Wysyłka wiadomości testowej SMTP (kanał diagnostyczny Guardiana)."""
from __future__ import annotations

from datetime import datetime

from ifg_guardian.core.time_compat import UTC
from ifg_guardian.plugins.ifg.smtp.config import _ensure_app_importable
from ifg_guardian.plugins.ifg.smtp.models import SmtpStageStatus, TestMailResult


def build_test_mail_body(
    *,
    host: str,
    workflow_id: str,
    app_version: str,
) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"Data: {ts}\n"
        f"Host: {host}\n"
        f"Guardian Workflow: {workflow_id}\n"
        f"Wersja IFG: {app_version}\n"
        "\n"
        "To jest wiadomość testowa wygenerowana przez Guardian.\n"
        "Nie pochodzi z synchronizacji KSeF.\n"
    )


def send_test_mail(
    *,
    config,
    recipients: list[str],
    workflow_id: str,
    app_version: str,
) -> TestMailResult:
    _ensure_app_importable()
    from app.integrations.email.smtp_client import SmtpSendError, send_email

    subject = "IFG SMTP Test"
    body = build_test_mail_body(
        host=config.host,
        workflow_id=workflow_id,
        app_version=app_version,
    )
    try:
        send_email(
            config=config,
            to_addrs=recipients,
            subject=subject,
            body_text=body,
        )
    except SmtpSendError as exc:
        return TestMailResult(
            sent=False,
            status=SmtpStageStatus.FAIL,
            message=str(exc),
            subject=subject,
            recipients=list(recipients),
        )
    return TestMailResult(
        sent=True,
        status=SmtpStageStatus.PASS,
        message=f"test mail sent to {len(recipients)} recipient(s)",
        subject=subject,
        recipients=list(recipients),
    )
