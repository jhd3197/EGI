"""Action-plan and task mutation routes (plan-09 §5, §7).

Permission model (plan-09 §7):
  * View plans/tasks .......... viewer
  * Create/update own tasks ... operator (operators may only change the state of
                                tasks assigned to themselves)
  * Create plans, assign tasks  commander (assigning a task to someone else, or
                                reassigning, requires commander)
  * Delete plans / tasks ...... admin

The "assigned to self" rule only bites when a real user account is presented; in
the dev/no-users bypass there is no identity to compare against, so it is skipped
(matching the rest of the server's permissive dev posture).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from auth import current_user, require_role
from models import ActionPlanUpdate, TaskCreate, TaskUpdate
from modules import action_plans, users

router = APIRouter()

require_viewer = require_role("viewer")
require_operator = require_role("operator")
require_commander = require_role("commander")
require_admin = require_role("admin")


def _is_commander(user: Optional[dict]) -> bool:
    return bool(user) and users.role_satisfies(user["role"], "commander")


# ── Action plans ─────────────────────────────────────────────────────────────

@router.post("/action-plans/{plan_id}/activate")
def activate_plan(plan_id: str, principal: str = Depends(require_commander)):
    return action_plans.activate_plan(plan_id, actor=principal)


@router.patch("/action-plans/{plan_id}")
def update_plan(plan_id: str, req: ActionPlanUpdate, principal: str = Depends(require_commander)):
    return action_plans.update_plan(plan_id, req, actor=principal)


@router.delete("/action-plans/{plan_id}")
def delete_plan(plan_id: str, principal: str = Depends(require_admin)):
    return action_plans.delete_plan(plan_id, actor=principal)


# ── Tasks ────────────────────────────────────────────────────────────────────

@router.get("/action-plans/{plan_id}/tasks")
def list_tasks(plan_id: str, principal: str = Depends(require_viewer)):
    return action_plans.list_tasks(plan_id)


@router.post("/action-plans/{plan_id}/tasks")
def create_task(
    plan_id: str,
    req: TaskCreate,
    authorization: Optional[str] = Header(default=None),
    principal: str = Depends(require_operator),
):
    user = current_user(authorization)
    # Assigning a task to someone other than yourself is a commander action.
    if req.assignee_id and user is not None:
        if req.assignee_id != user["id"] and not _is_commander(user):
            raise HTTPException(status_code=403, detail="Assigning tasks requires commander")
    return action_plans.create_task(plan_id, req, actor=principal)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    req: TaskUpdate,
    authorization: Optional[str] = Header(default=None),
    principal: str = Depends(require_operator),
):
    user = current_user(authorization)
    fields = req.model_dump(exclude_unset=True)

    # Reassignment (changing assignee_id) requires commander.
    if "assignee_id" in fields and user is not None and not _is_commander(user):
        existing = action_plans.get_task(task_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if fields["assignee_id"] != existing.get("assignee_id"):
            raise HTTPException(status_code=403, detail="Reassigning tasks requires commander")

    # A plain operator may only update tasks assigned to themselves.
    if user is not None and not _is_commander(user):
        existing = action_plans.get_task(task_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if existing.get("assignee_id") != user["id"]:
            raise HTTPException(
                status_code=403, detail="Operators may only update tasks assigned to themselves"
            )
    return action_plans.update_task(task_id, req, actor=principal)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, principal: str = Depends(require_admin)):
    return action_plans.delete_task(task_id, actor=principal)
