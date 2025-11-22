from __future__ import annotations

"""
Minimal SMTP email sender used for verification and admin contact.

In tests, monkeypatch send_email to capture outgoing messages without
performing network I/O.
"""

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.settings import Settings, get_settings

_log = logging.getLogger("email")


def _bool_env(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def send_email(to: str, subject: str, body: str, settings: Optional[Settings] = None) -> None:
    """Send a plain text email using SMTP (Gmail / generic SMTP).

    Behavior:
    - If EMAIL_ENABLED is falsey, log and return without sending.
    - Reads SMTP details from Settings (populated from env vars).
    - Raises RuntimeError when enabled but required config is missing.
    - Logs success / failure for observability.

    Tests monkeypatch this function; they should not require environment.
    """
    cfg = settings or get_settings()

    if not getattr(cfg, "EMAIL_ENABLED", False):
        _log.info("Email disabled (EMAIL_ENABLED not truthy); skipping send to %s", to)
        return

    smtp_host = cfg.SMTP_HOST
    smtp_port = int(cfg.SMTP_PORT or 587)
    smtp_user = cfg.SMTP_USERNAME
    smtp_pass = cfg.SMTP_PASSWORD
    email_from = cfg.EMAIL_FROM or smtp_user
    use_tls = bool(cfg.SMTP_USE_TLS)

    missing = [name for name, val in [
        ("SMTP host", smtp_host),
        ("From address", email_from),
    ] if not val]
    if missing:
        raise RuntimeError(f"Email configuration incomplete: missing {', '.join(missing)}")

    msg = EmailMessage()
    msg["From"] = email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body or "", subtype="plain")

    _log.info("Sending email to %s (subject=%r)", to, subject)
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as s:
            s.ehlo()
            if use_tls:
                try:
                    s.starttls()
                    s.ehlo()
                except Exception as tls_err:
                    _log.error("STARTTLS failed: %s", tls_err, exc_info=True)
                    raise RuntimeError(f"STARTTLS failed: {tls_err}") from tls_err
            if smtp_user:
                try:
                    s.login(smtp_user, smtp_pass or "")
                except Exception as auth_err:
                    _log.error("SMTP auth failed: %s", auth_err, exc_info=True)
                    raise RuntimeError(f"SMTP auth failed: {auth_err}") from auth_err
            try:
                s.send_message(msg)
            except Exception as send_err:
                _log.error("SMTP send failed: %s", send_err, exc_info=True)
                raise RuntimeError(f"SMTP send failed: {send_err}") from send_err
    except RuntimeError:
        # Re-raise explicit config/auth errors so callers can handle.
        _log.error("Email send failed (runtime error) to %s", to, exc_info=True)
        raise
    except Exception as e:  # Generic unexpected failures.
        _log.error("Email send failed to %s: %s", to, e, exc_info=True)
        raise RuntimeError(f"Failed to send email: {e}") from e
    else:
        _log.info("Email sent successfully to %s", to)
