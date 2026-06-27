"""Operation + action-plan-list routes (plan-09 §5).

Operations are the `events` table viewed as active operational cases. Viewing is
``viewer``-level; creating / mutating / opening / closing an operation and
creating action-plan versions are ``commander``-level (plan-09 §7). The legacy
``/events`` routes remain for backward compatibility (see routes/events.py).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import require_role
from models import ActionPlanCreate, OperationClose, OperationCreate, OperationUpdate
from modules import action_plans, operations

router = APIRouter()

require_viewer = require_role("viewer")
require_commander = require_role("commander")


@router.get("/operations")
def list_operations(
    status: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    is_practice: Optional[int] = Query(None),
    principal: str = Depends(require_viewer),
):
    return operations.list_operations(status=status, region=region, is_practice=is_practice)


@router.post("/operations")
def create_operation(req: OperationCreate, principal: str = Depends(require_commander)):
    return operations.create_operation(req, actor=principal)


@router.get("/operations/{op_id}")
def get_operation(op_id: str, principal: str = Depends(require_viewer)):
    return operations.get_operation(op_id)


@router.patch("/operations/{op_id}")
def update_operation(op_id: str, req: OperationUpdate, principal: str = Depends(require_commander)):
    return operations.update_operation(op_id, req, actor=principal)


@router.post("/operations/{op_id}/close")
def close_operation(op_id: str, req: OperationClose, principal: str = Depends(require_commander)):
    return operations.close_operation(op_id, req.reason, actor=principal)


@router.post("/operations/{op_id}/reopen")
def reopen_operation(op_id: str, principal: str = Depends(require_commander)):
    return operations.reopen_operation(op_id, actor=principal)


# ── Action plans nested under an operation ───────────────────────────────────

@router.get("/operations/{op_id}/action-plans")
def list_action_plans(op_id: str, principal: str = Depends(require_viewer)):
    return action_plans.list_plans(op_id)


@router.post("/operations/{op_id}/action-plans")
def create_action_plan(
    op_id: str, req: ActionPlanCreate, principal: str = Depends(require_commander)
):
    return action_plans.create_plan(op_id, req, actor=principal)
