"""Authentication & role-based access control (plan-08).

Originally this module validated a comma-separated ``OPERATOR_TOKENS`` env var.
Plan-08 replaces that with real user accounts (``modules/users.py``) while
keeping the same ``Authorization: Bearer <token>`` wire shape, so clients need no
changes.

Three FastAPI dependencies:

  * ``require_role(min_role)`` — the workhorse. Accepts, in order:
        1. a valid **user token** whose role satisfies ``min_role``;
        2. a static ``OPERATOR_TOKENS`` token — **deprecated**, treated as
           operator-level only, and logged so operators migrate;
        3. a dev fallback: if no users exist *and* no static tokens are
           configured, auth is disabled (local dev / test suite).
    It returns a short, non-secret *principal* string for audit attribution.
  * ``require_operator`` — a backward-compatible alias for
    ``require_role("operator")`` so existing call sites keep working.
  * ``require_user`` — require a genuine user token (no static / dev bypass);
    returns the full user dict. Used by ``/auth/me``, ``/auth/logout``, etc.

Tokens and passwords are never logged. ``token_principal`` / ``user_principal``
return short labels safe for the audit log.
"""

import hmac
import logging
import os
from typing import List, Optional

from fastapi import Header, HTTPException

logger = logging.getLogger("egi.auth")

# Identity used when auth is disabled (no users, no tokens). Audit logs record
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


def user_principal(user: dict) -> str:
    """A short, attributable label for an authenticated user (no secrets)."""
    return f"user:{user['id']}:{user.get('name') or user.get('email')}"


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _match(token: str, configured: List[str]) -> bool:
    # Constant-time compare against each configured token to avoid leaking which
    # prefix matched via timing.
    return any(hmac.compare_digest(token, c) for c in configured)


def _audit_failure(token: Optional[str], detail: str) -> None:
    from modules import audit

    audit.log_action(token_principal(token), "auth_failure", "auth", None, detail=detail)


def current_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    """Resolve a valid user bearer token to its user dict, or ``None``.

    Never raises — use this when an endpoint wants the caller's identity but
    does not strictly require it.
    """
    token = _extract_bearer(authorization)
    if not token:
        return None
    from modules import users

    return users.get_user_for_token(token)


def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Require a genuine user token. Returns the user dict or raises 401.

    Unlike ``require_role``, this has no static-token or dev bypass: the caller
    must be a real account (used where we need a concrete user identity).
    """
    user = current_user(authorization)
    if user:
        return user
    _audit_failure(_extract_bearer(authorization), "invalid or missing user token")
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(min_role: str):
    """Build a dependency that requires a principal at >= ``min_role``.

    Returns a callable suitable for ``Depends(...)`` whose value is the audit
    principal string. Raises 401 (no/invalid credentials) or 403 (valid but
    under-privileged).
    """

    def dependency(authorization: Optional[str] = Header(default=None)) -> str:
        from modules import audit, users

        token = _extract_bearer(authorization)

        # 1. Real user account (the primary path).
        if token:
            user = users.get_user_for_token(token)
            if user:
                if not users.role_satisfies(user["role"], min_role):
                    audit.log_action(
                        user_principal(user), "auth_forbidden", "auth", None,
                        detail=f"role {user['role']} < required {min_role}",
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=f"Role '{min_role}' required",
                    )
                return user_principal(user)

        # 2. Deprecated static operator token (operator-level only).
        configured = get_operator_tokens()
        if configured:
            if token and _match(token, configured):
                logger.warning(
                    "Deprecated static OPERATOR_TOKENS used; migrate to user "
                    "accounts (plan-08). Support will be removed in a future release."
                )
                if not users.role_satisfies("operator", min_role):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"Role '{min_role}' required; static operator tokens "
                            "grant only operator-level access"
                        ),
                    )
                return token_principal(token)
            _audit_failure(token, "invalid or missing operator token")
            raise HTTPException(
                status_code=401,
                detail="Operator authorization required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. No static tokens configured: dev fallback only while no users exist.
        if users.count_users() == 0:
            return ANON_DEV_PRINCIPAL

        # Users exist but the caller presented no valid token.
        _audit_failure(token, "invalid or missing token")
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dependency


# Backward-compatible alias: existing routes use ``Depends(require_operator)``.
# Now an operator-level RBAC check that still accepts deprecated static tokens.
require_operator = require_role("operator")
