"""Tests for the email module's `send_email` and template functions.

`smtplib.SMTP` is mocked throughout — the automated suite must not depend
on a live Mailpit connection (Mailpit is only for manual sanity checks at
localhost:1025 / localhost:8025).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.modules.email.service import send_email
from app.modules.email.templates import invitation_email, password_reset_email


def test_send_email_connects_and_sends_message():
    with patch("app.modules.email.service.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        send_email("someone@example.com", "Hello", "<p>Hi</p>")

        mock_smtp_cls.assert_called_once()
        mock_smtp.send_message.assert_called_once()
        sent_message = mock_smtp.send_message.call_args[0][0]
        assert sent_message["To"] == "someone@example.com"
        assert sent_message["Subject"] == "Hello"


def test_send_email_starts_tls_when_configured():
    with patch("app.modules.email.service.settings") as mock_settings:
        mock_settings.smtp_host = "localhost"
        mock_settings.smtp_port = 1025
        mock_settings.smtp_use_tls = True
        mock_settings.smtp_username = None
        mock_settings.smtp_password = None
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_from_name = "Shopora"

        with patch("app.modules.email.service.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

            send_email("someone@example.com", "Hello", "<p>Hi</p>")

            mock_smtp.starttls.assert_called_once()


def test_send_email_logs_in_when_username_configured():
    with patch("app.modules.email.service.settings") as mock_settings:
        mock_settings.smtp_host = "localhost"
        mock_settings.smtp_port = 1025
        mock_settings.smtp_use_tls = False
        mock_settings.smtp_username = "user"
        mock_settings.smtp_password = "pass"
        mock_settings.smtp_from_email = "noreply@example.com"
        mock_settings.smtp_from_name = "Shopora"

        with patch("app.modules.email.service.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

            send_email("someone@example.com", "Hello", "<p>Hi</p>")

            mock_smtp.login.assert_called_once_with("user", "pass")


def test_invitation_email_contains_role_url_and_expiry():
    expires_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    html = invitation_email("Alice", "manager", "https://app.example.com/accept?token=abc", expires_at)

    assert "Alice" in html
    assert "manager" in html
    assert "https://app.example.com/accept?token=abc" in html
    assert "2026-01-01" in html


def test_password_reset_email_contains_url_and_expiry():
    expires_at = datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc)
    html = password_reset_email("Bob", "https://app.example.com/reset?token=xyz", expires_at)

    assert "Bob" in html
    assert "https://app.example.com/reset?token=xyz" in html
    assert "2026-01-01" in html
