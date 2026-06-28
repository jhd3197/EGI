"""HTTP adapters for the Search & Rescue operations workflow (plan-26).

Reads are ``viewer``-level so any volunteer can see operations. Creating /
mutating an operation is ``viewer``-level too in Phase 1 (any authenticated user,
with the dev bypass when no users exist); Phase 6 tightens operation creation to
a verified account. Namespaced under ``/sar`` so it never collides with the
plan-09 ``/operations`` (events) routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from auth import current_user, require_role
from models import (
    SarOperationCreate,
    SarOperationStatusUpdate,
    SarOperationUpdate,
)
from modules import sar

router = APIRouter()

require_viewer = require_role("viewer")


def _user_id(authorization: Optional[str]) -> Optional[str]:
    user = current_user(authorization)
    return user["id"] if user else None


# ── Operations CRUD (plan-26 Phase 1) ────────────────────────────────────────


@router.get("/sar/operations")
def list_operations(
    disaster_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    principal: str = Depends(require_viewer),
):
    return sar.list_operations(disaster_id=disaster_id, status=status)


@router.post("/sar/operations")
def create_operation(
    req: SarOperationCreate,
    principal: str = Depends(require_viewer),
    authorization: Optional[str] = Header(default=None),
):
    return sar.create_operation(req, actor=principal, user_id=_user_id(authorization))


@router.get("/sar/operations/{op_id}")
def get_operation(op_id: str, principal: str = Depends(require_viewer)):
    return sar.get_operation(op_id)


@router.patch("/sar/operations/{op_id}")
def update_operation(
    op_id: str, req: SarOperationUpdate, principal: str = Depends(require_viewer)
):
    return sar.update_operation(op_id, req, actor=principal)


@router.patch("/sar/operations/{op_id}/status")
def set_operation_status(
    op_id: str, req: SarOperationStatusUpdate, principal: str = Depends(require_viewer)
):
    return sar.set_status(op_id, req.status, req.reason, actor=principal)
