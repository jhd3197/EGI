"""Operator (moderator) authentication via static bearer tokens.

Moderation and duplicate-review endpoints change *public* data, so they must be
attributable and protected (plan-07 §6). We keep it lightweight — no user table,
no sessions — to suit a community server: a comma-separated ``OPERATOR_TOKENS``
env var holds one or more secure random strings, and protected routes require
``Authorization: Bearer <token>``.

Degradation rule (matches CORS/rate-limit): if ``OPERATOR_TOKENS`` is unset or
empty, operator auth is **disabled** so local dev and the test suite work out of
the box. A public deployment MUST set the variable; the deployment guide and
``.env.example`` say so, and ``operator_auth_enabled()`` lets callers warn.

Tokens are never logged in full. ``token_principal()`` returns a short,
non-reversible label (``op:<prefix>…``) so audit logs can attribute an action
without storing the secret.
"""

import hmac
import os
from typing import List, Optional

from fastapi import Header, HTTPException

# Identity used when auth is disabled (no tokens configured). Audit logs record
# this so it's obvious the action was taken on an unprotected dev server.
ANON_DEV_PRINCIPAL = "op:dev-unauthenticated"


def get_operator_tokens() -> List[str]:
    raw = os.environ.get("OPERATOR_TOKENS", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def operator_auth_enabled() -> bool:
    return len(get_operator_tokens()) > 0


def token_principal(token: Optional[str]) -> str:
    """A short, non-secret label for a token, safe to put in audit logs."""
    if not token:
        return "op:anonymous"
    return f"op:{token[:6]}…"


def _match(token: str, configured: List[str]) -> bool:
    # Constant-time compare against each configured token to avoid leaking which
    # prefix matched via timing.
    return any(hmac.compare_digest(token, c) for c in configured)


def require_operator(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency. Returns the operator principal or raises 401.

    When no tokens are configured, auth is disabled and a dev principal is
    returned (the request is allowed). When tokens ARE configured, a valid
    ``Authorization: Bearer <token>`` header is required.
    """
    configured = get_operator_tokens()
    if not configured:
        return ANON_DEV_PRINCIPAL

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token or not _match(token, configured):
        # Log the failure (never the attempted token). Successful auth is
        # implicitly recorded by the action's own audit row, so we don't
        # double-log it here.
        from modules import audit

        audit.log_action(
            token_principal(token), "auth_failure", "auth", None,
            detail="invalid or missing operator token",
        )
        raise HTTPException(
            status_code=401,
            detail="Operator authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_principal(token)
