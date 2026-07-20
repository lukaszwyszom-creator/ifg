"""Testy parsowania SMTP_FROM i envelope sender."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.integrations.email.smtp_client import (
    SmtpConfig,
    SmtpFromParseError,
    SmtpSendError,
    parse_smtp_from,
    send_email,
)


class TestParseSmtpFrom:
    def test_plain_address(self):
        header, envelope = parse_smtp_from("ds723@ikonastudio.pl")
        assert envelope == "ds723@ikonastudio.pl"
        assert "ds723@ikonastudio.pl" in header

    def test_display_name_with_brackets(self):
        raw = 'IFG [DS 723+] <ds723@ikonastudio.pl>'
        header, envelope = parse_smtp_from(raw)
        assert envelope == "ds723@ikonastudio.pl"
        assert header == '"IFG [DS 723+]" <ds723@ikonastudio.pl>'

    def test_quoted_full_value(self):
        raw = '"IFG [DS 723+] <ds723@ikonastudio.pl>"'
        header, envelope = parse_smtp_from(raw)
        assert envelope == "ds723@ikonastudio.pl"
        assert header == '"IFG [DS 723+]" <ds723@ikonastudio.pl>'

    def test_display_name_only_rejected(self):
        with pytest.raises(SmtpFromParseError, match="SMTP_FROM"):
            parse_smtp_from("IFG")

    def test_empty_rejected(self):
        with pytest.raises(SmtpFromParseError, match="empty"):
            parse_smtp_from("")
        with pytest.raises(SmtpFromParseError, match="empty"):
            parse_smtp_from("   ")


class TestSendEmailEnvelope:
    def _config(self, from_addr: str) -> SmtpConfig:
        return SmtpConfig(
            host="smtp.test",
            port=587,
            user="user@test",
            password="secret",
            from_addr=from_addr,
            use_tls=True,
        )

    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_plain_address_envelope(self, mock_smtp_cls):
        instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = instance

        send_email(
            config=self._config("ds723@ikonastudio.pl"),
            to_addrs=["ops@test.com"],
            subject="Test",
            body_text="body",
        )

        _, kwargs = instance.send_message.call_args
        assert kwargs["from_addr"] == "ds723@ikonastudio.pl"
        message = instance.send_message.call_args.args[0]
        assert "ds723@ikonastudio.pl" in message["From"]

    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_display_name_envelope_uses_bare_address(self, mock_smtp_cls):
        instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = instance

        send_email(
            config=self._config("IFG [DS 723+] <ds723@ikonastudio.pl>"),
            to_addrs=["ops@test.com"],
            subject="Test",
            body_text="body",
        )

        _, kwargs = instance.send_message.call_args
        assert kwargs["from_addr"] == "ds723@ikonastudio.pl"
        message = instance.send_message.call_args.args[0]
        assert message["From"] == '"IFG [DS 723+]" <ds723@ikonastudio.pl>'

    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_invalid_from_no_smtp_connection(self, mock_smtp_cls):
        with pytest.raises(SmtpSendError, match="SMTP_FROM"):
            send_email(
                config=self._config("IFG"),
                to_addrs=["ops@test.com"],
                subject="Test",
                body_text="body",
            )
        mock_smtp_cls.assert_not_called()

    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_production_recipient_not_used_as_envelope_sender(self, mock_smtp_cls):
        """Regression: PURCHASE_SYNC_NOTIFY_RECIPIENTS must not become MAIL FROM."""
        instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = instance

        send_email(
            config=self._config("IFG [DS 723+] <ds723@ikonastudio.pl>"),
            to_addrs=["lukasz@ikonastudio.pl"],
            subject="IFG — nowe faktury zakupowe z KSeF",
            body_text="body",
        )

        _, kwargs = instance.send_message.call_args
        envelope = kwargs["from_addr"]
        recipients = kwargs["to_addrs"]
        assert envelope == "ds723@ikonastudio.pl"
        assert recipients == ["lukasz@ikonastudio.pl"]
        assert envelope not in recipients
        assert recipients[0] != envelope

    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_multiple_recipients(self, mock_smtp_cls):
        instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = instance

        send_email(
            config=self._config("ds723@ikonastudio.pl"),
            to_addrs=["a@test.com", "b@test.com"],
            subject="Test",
            body_text="body",
        )

        _, kwargs = instance.send_message.call_args
        assert kwargs["to_addrs"] == ["a@test.com", "b@test.com"]
