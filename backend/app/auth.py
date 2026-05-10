"""Simple bearer-token admin auth.

The admin password is the bearer token. The frontend POSTs the password to
/api/admin/login, which echoes it back as the token after validation. The
backend validates each admin request via constant-time comparison.

This is intentionally minimal — Phase 2 just needs to keep ingestion + reindex
out of public hands during local/dev use. Replace with real auth (Entra ID)
when deploying.
"""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .config import settings


def _check(token: str | None) -> None:
    expected = settings.admin_password
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin password not configured on the server.",
        )
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency. Expects `Authorization: Bearer <password>`."""
    token: str | None = None
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
    _check(token)


def verify_password(password: str) -> bool:
    expected = settings.admin_password
    if not expected:
        return False
    return hmac.compare_digest(password, expected)
