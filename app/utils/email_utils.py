from __future__ import annotations

"""
Minimal SMTP email sender used for verification and admin contact.

In tests, monkeypatch send_email to capture outgoing messages without
performing network I/O.
"""

import smtplib
from email.message import EmailMessage
from typing import Optional

from app.settings import Settings, get_settings


def send_email(to: str, subject: str, body: str, settings: Optional[Settings] = None) -> None:
    """
    Send a plain text email using SMTP.

    If SMTP_HOST or EMAIL_FROM is not configured, raise RuntimeError
    instead of silently failing.
    """
    cfg = settings or get_settings()
    if not cfg.SMTP_HOST or not cfg.EMAIL_FROM:
        raise RuntimeError("SMTP_HOST and EMAIL_FROM must be configured to send email")

    msg = EmailMessage()
    msg["From"] = cfg.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body or "", subtype="plain")

    if cfg.SMTP_USE_TLS:
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as s:
            s.starttls()
            if cfg.SMTP_USERNAME:
                s.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as s:
            if cfg.SMTP_USERNAME:
                s.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD or "")
            s.send_message(msg)
