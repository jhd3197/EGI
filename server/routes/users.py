"""User management routes (plan-08 §6). Admin-only CRUD over accounts.

All endpoints require an ``admin`` principal (``require_role('admin')``). Note a
deprecated static operator token is operator-level, so it canNOT reach these —
user management deliberately requires a real admin account.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_admin
from modules import audit, users
from routes.dependencies import get_or_404

router = APIRouter(prefix="/users")


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "viewer"
    name: Optional[str] = None
    active: int = 1


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[int] = None


class ResetPasswordRequest(BaseModel):
    # If omitted, a strong temporary password is generated and returned once.
    password: Optional[str] = None


@router.get("")
def list_all(operator: str = Depends(require_admin)):
    return {"users": users.list_users()}


@router.post("")
def create(req: CreateUserRequest, operator: str = Depends(require_admin)):
    try:
        user = users.create_user(
            email=req.email, password=req.password, role=req.role,
            name=req.name, active=req.active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit.log_action(operator, "user_create", "user", user["id"], detail=f"role={req.role}")
    # Best-effort welcome email (plan-11). Never blocks account creation; degrades
    # to the log driver when no email provider is configured.
    try:
        from modules import email as email_mod

        email_mod.send_welcome(user, actor=operator)
    except Exception:  # pragma: no cover - notification must never break CRUD
        pass
    return {"user": users.public_user(user)}


@router.patch("/{user_id}")
def patch(user_id: str, req: UpdateUserRequest, operator: str = Depends(require_admin)):
    try:
        user = users.update_user(
            user_id, name=req.name, role=req.role, active=req.active
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    audit.log_action(operator, "user_update", "user", user_id)
    return {"user": users.public_user(user)}


@router.delete("/{user_id}")
def delete(user_id: str, operator: str = Depends(require_admin)):
    if not users.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    audit.log_action(operator, "user_delete", "user", user_id)
    return {"ok": True}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str, req: ResetPasswordRequest, operator: str = Depends(require_admin)
):
    """Set a user's password. With no body, generate a one-time temp password.

    Resetting the password revokes all of the user's existing tokens (see
    ``users.set_password``), forcing a fresh login.
    """
    get_or_404(users.get_user_by_id, user_id, "User")
    temp = None
    password = req.password
    if not password:
        password = users.generate_token()  # strong, URL-safe one-time password
        temp = password
    users.set_password(user_id, password)
    audit.log_action(operator, "user_reset_password", "user", user_id)
    out = {"ok": True}
    if temp is not None:
        out["temporary_password"] = temp
    return out
