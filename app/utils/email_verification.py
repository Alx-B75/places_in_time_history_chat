from __future__ import annotations

"""
Self-contained token creation and verification for email verification.

We use an HMAC-SHA256 signature over a JSON payload with base64url encoding.
The payload includes user_id, email, and issued-at timestamp (iat). The secret
is Settings.EMAIL_VERIFICATION_SECRET.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Tuple

from fastapi import HTTPException, status

from app.settings import Settings, get_settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode("ascii"))


def create_email_verification_token(user_id: int, email: str, settings: Settings | None = None) -> str:
    """
    Create a signed verification token including user_id, email, and an expiry (48h by default on verify).
    """
    cfg = settings or get_settings()
    header = {"alg": "HS256", "typ": "EVT"}
    payload = {"uid": int(user_id), "email": email, "iat": int(time.time())}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("utf-8")
    sig = hmac.new(cfg.EMAIL_VERIFICATION_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    s = _b64url(sig)
    return f"{h}.{p}.{s}"


def verify_email_verification_token(token: str, settings: Settings | None = None, max_age_seconds: int = 172800) -> Tuple[int, str]:
    """
    Validate a verification token and return (user_id, email) on success.
    Raise HTTPException on invalid or expired tokens.
    """
    cfg = settings or get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token format")
    h_b64, p_b64, s_b64 = parts
    try:
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(cfg.EMAIL_VERIFICATION_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(s_b64)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token encoding")
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")
    try:
        payload = json.loads(_b64url_decode(p_b64))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token payload")
    iat = int(payload.get("iat", 0))
    if int(time.time()) - iat > int(max_age_seconds):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token expired")
    uid = int(payload.get("uid"))
    email = str(payload.get("email"))
    if not uid or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token claims")
    return uid, email
