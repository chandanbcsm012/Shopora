"""Business logic for the email module: send transactional HTML emails
(invitations, password resets) via stdlib `smtplib`. No database table —
this module exists purely as an infrastructure service other modules call
directly (via FastAPI `BackgroundTasks`), the same shape as the `media`
module (see docs/CONTRACTS.md).
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


def send_email(to: str, subject: str, html_body: str) -> None:
    """Build and send a single HTML email synchronously. Callers (routers)
    should invoke this via `BackgroundTasks.add_task(send_email, ...)` so
    the HTTP response doesn't block on SMTP."""

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to
    message.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
