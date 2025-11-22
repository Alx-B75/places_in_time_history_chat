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
        _log.debug("Email disabled (EMAIL_ENABLED not truthy); skipping send to %s", to)
        return

    # Support alternative variable names (EMAIL_SMTP_HOST, EMAIL_FROM_ADDRESS) if present in the environment.
    # This allows deploy environments to use either legacy or new names without code changes.
    smtp_host = os.getenv("EMAIL_SMTP_HOST") or cfg.SMTP_HOST
    smtp_port_raw = os.getenv("EMAIL_SMTP_PORT") or str(cfg.SMTP_PORT)
    smtp_port = int(smtp_port_raw or "587")
    smtp_user = os.getenv("EMAIL_SMTP_USERNAME") or cfg.SMTP_USERNAME
    smtp_pass = os.getenv("EMAIL_SMTP_PASSWORD") or cfg.SMTP_PASSWORD
    email_from = os.getenv("EMAIL_FROM_ADDRESS") or cfg.EMAIL_FROM or smtp_user
    use_tls = _bool_env(os.getenv("EMAIL_USE_TLS")) if os.getenv("EMAIL_USE_TLS") is not None else cfg.SMTP_USE_TLS

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
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
                s.ehlo()
                try:
                    s.starttls()
                    s.ehlo()
                except Exception as tls_err:
                    _log.warning("TLS negotiation failed: %s", tls_err)
                if smtp_user:
                    try:
                        s.login(smtp_user, smtp_pass or "")
                    except Exception as auth_err:
                        raise RuntimeError(f"SMTP auth failed: {auth_err}") from auth_err
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
                if smtp_user:
                    try:
                        s.login(smtp_user, smtp_pass or "")
                    except Exception as auth_err:
                        raise RuntimeError(f"SMTP auth failed: {auth_err}") from auth_err
                s.send_message(msg)
    except RuntimeError:
        # Re-raise explicit config/auth errors so callers can handle.
        _log.error("Email send failed (runtime error) to %s", to, exc_info=True)
        raise
    except Exception as e:  # Generic unexpected failures.
        _log.error("Email send failed to %s: %s", to, e, exc_info=True)
        raise RuntimeError(f"Failed to send email: {e}") from e
    else:
        _log.info("Email sent successfully to %s", to)
