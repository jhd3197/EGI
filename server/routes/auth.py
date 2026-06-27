"""Authentication routes (plan-08 §6): login, logout, token management, profile.

The client exchanges email+password at ``POST /auth/login`` for an opaque bearer
token, then sends ``Authorization: Bearer <token>`` on every protected call —
the same wire shape the PWA/mobile clients already use. Login is rate limited
(reusing the shared in-memory limiter) to blunt credential stuffing.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import _extract_bearer, require_user
from models import PasswordResetConfirm, PasswordResetRequest
from modules import audit, users
from ratelimit import rate_limit

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateTokenRequest(BaseModel):
    name: Optional[str] = None
    expires_at: Optional[str] = None


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("/login", dependencies=[Depends(rate_limit)])
def login(req: LoginRequest, request: Request):
    """Exchange email + password for a fresh bearer token."""
    user = users.authenticate(req.email, req.password)
    if not user:
        # Do not reveal whether the email exists or the password was wrong.
        audit.log_action(
            "op:anonymous", "login_failure", "auth", None,
            detail=f"email={(req.email or '').strip().lower()}",
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    ip = _client_ip(request)
    users.touch_login(user["id"], ip)
    token = users.create_token(user["id"], name="login")
    audit.log_action(
        f"user:{user['id']}:{user.get('name') or user['email']}",
        "login", "auth", user["id"], detail=f"ip={ip}",
    )
    return {"token": token["token"], "user": users.public_user(user)}


@router.post("/logout")
def logout(request: Request, user: dict = Depends(require_user)):
    """Revoke the token used for this request."""
    token = _extract_bearer(request.headers.get("authorization"))
    revoked = False
    if token:
        revoked = users.revoke_token(users.hash_token(token), user_id=user["id"])
    audit.log_action(
        f"user:{user['id']}:{user.get('name') or user['email']}",
        "logout", "auth", user["id"],
    )
    return {"ok": True, "revoked": revoked}


@router.post("/forgot-password", dependencies=[Depends(rate_limit)])
def forgot_password(req: PasswordResetRequest):
    """Begin a password reset (plan-11). Always returns ok (no email enumeration).

    If the email belongs to an active account, mint a single-use reset token and
    email a reset link. The token never appears in the response.
    """
    user = users.get_user_by_email(req.email)
    if user and user.get("active"):
        reset = users.create_password_reset(user["id"])
        audit.log_action(
            f"user:{user['id']}:{user.get('name') or user['email']}",
            "password_reset_request", "auth", user["id"],
        )
        try:
            from modules import email as email_mod

            email_mod.send_password_reset(
                user, reset["token"], ttl_minutes=reset["ttl_minutes"]
            )
        except Exception:  # pragma: no cover - never reveal failures to the caller
            pass
    return {"ok": True, "message": "If the email exists, a reset link was sent."}


@router.post("/reset-password", dependencies=[Depends(rate_limit)])
def reset_password(req: PasswordResetConfirm):
    """Complete a password reset with a token from the reset email (plan-11)."""
    if not users.consume_password_reset(req.token, req.password):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    audit.log_action("op:anonymous", "password_reset_complete", "auth", None)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(require_user)):
    """Current user's profile (no password hash)."""
    return {"user": users.public_user(user)}


@router.get("/tokens")
def list_my_tokens(user: dict = Depends(require_user)):
    """Metadata for the current user's tokens (never the raw token values)."""
    return {"tokens": users.list_tokens(user["id"])}


@router.post("/tokens")
def create_my_token(req: CreateTokenRequest, user: dict = Depends(require_user)):
    """Mint an additional token (e.g. for the CLI or a second device).

    The raw token is returned exactly once.
    """
    token = users.create_token(user["id"], name=req.name, expires_at=req.expires_at)
    audit.log_action(
        f"user:{user['id']}:{user.get('name') or user['email']}",
        "token_create", "auth", user["id"], detail=f"name={req.name}",
    )
    return token


@router.delete("/tokens/{token_hash}")
def revoke_my_token(token_hash: str, user: dict = Depends(require_user)):
    """Revoke one of the current user's tokens by its hash."""
    revoked = users.revoke_token(token_hash, user_id=user["id"])
    if not revoked:
        raise HTTPException(status_code=404, detail="Token not found")
    audit.log_action(
        f"user:{user['id']}:{user.get('name') or user['email']}",
        "token_revoke", "auth", user["id"],
    )
    return {"ok": True}
