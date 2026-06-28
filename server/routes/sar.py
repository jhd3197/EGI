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
    FieldReportCreate,
    FieldReportResolve,
    SarOperationCreate,
    SarOperationStatusUpdate,
    SarOperationUpdate,
    SarSyncPayload,
    SarTaskCreate,
    SarTaskUpdate,
    SectorClaim,
    SectorStatusUpdate,
    VolunteerCheckin,
    VolunteerJoin,
)
from modules import sar
from ratelimit import rate_limit

router = APIRouter()

require_viewer = require_role("viewer")
require_operator = require_role("operator")


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


# ── Volunteers + sectors (plan-26 Phase 3) ────────────────────────────────────


@router.post("/sar/operations/{op_id}/join")
def join_operation(
    op_id: str,
    req: VolunteerJoin,
    principal: str = Depends(require_viewer),
    authorization: Optional[str] = Header(default=None),
):
    return sar.join_operation(op_id, req, actor=principal, user_id=_user_id(authorization))


@router.post("/sar/sectors/{sector_id}/claim")
def claim_sector(sector_id: str, req: SectorClaim, principal: str = Depends(require_viewer)):
    return sar.claim_sector(sector_id, req, actor=principal)


@router.post("/sar/sectors/{sector_id}/release")
def release_sector(sector_id: str, principal: str = Depends(require_viewer)):
    return sar.release_sector(sector_id, actor=principal)


@router.patch("/sar/sectors/{sector_id}")
def update_sector(sector_id: str, req: SectorStatusUpdate, principal: str = Depends(require_viewer)):
    return sar.update_sector(sector_id, req, actor=principal)


@router.post("/sar/sectors/{sector_id}/checkin")
def checkin_sector(sector_id: str, req: VolunteerCheckin, principal: str = Depends(require_viewer)):
    return sar.checkin_sector(sector_id, req.volunteer_id, actor=principal)


@router.post("/sar/volunteers/{volunteer_id}/checkout")
def checkout_volunteer(volunteer_id: str, principal: str = Depends(require_viewer)):
    return sar.checkout_sector(volunteer_id, actor=principal)


# ── Tasks (plan-26 Phase 3) ───────────────────────────────────────────────────


@router.post("/sar/operations/{op_id}/tasks")
def add_task(op_id: str, req: SarTaskCreate, principal: str = Depends(require_viewer)):
    return sar.add_task(op_id, req, actor=principal)


@router.patch("/sar/tasks/{task_id}")
def update_task(task_id: str, req: SarTaskUpdate, principal: str = Depends(require_viewer)):
    return sar.update_task(task_id, req, actor=principal)


@router.delete("/sar/tasks/{task_id}")
def delete_task(task_id: str, principal: str = Depends(require_viewer)):
    return sar.delete_task(task_id, actor=principal)


# ── Field reports + mesh/cloud sync (plan-26 Phase 4) ─────────────────────────


@router.get("/sar/operations/{op_id}/field-reports")
def list_field_reports(
    op_id: str,
    only_pending: bool = Query(False),
    principal: str = Depends(require_viewer),
):
    return sar.list_field_reports(op_id, only_pending=only_pending)


@router.post("/sar/operations/{op_id}/field-reports", dependencies=[Depends(rate_limit)])
def create_field_report(
    op_id: str,
    req: FieldReportCreate,
    principal: str = Depends(require_viewer),
    authorization: Optional[str] = Header(default=None),
):
    return sar.create_field_report(op_id, req, actor=principal, user_id=_user_id(authorization))


@router.post("/sar/field-reports/{fr_id}/resolve")
def resolve_field_report(
    fr_id: str, req: FieldReportResolve, principal: str = Depends(require_operator)
):
    """Confirm/dismiss a field report (plan-26 Phase 6) — operator-gated. A
    confirmed ``found`` report applies the registry status update."""
    return sar.resolve_field_report(fr_id, req, actor=principal)


@router.get("/sar/sync")
def sar_sync_download(since: Optional[str] = Query(None), principal: str = Depends(require_viewer)):
    return sar.sync_download(since=since)


@router.post("/sar/sync")
def sar_sync_upload(payload: SarSyncPayload, principal: str = Depends(require_viewer)):
    return sar.sync_upload(payload)
