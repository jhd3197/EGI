"""HTTP adapters for the Search & Rescue operations workflow (plan-26).

Access model (plan-26 §4.4 + Phase 6):

  * **Reads are public** — anonymous volunteers and family need to see operations,
    sectors, and field reports without an account.
  * **Volunteer actions are public** (join, claim/release a sector, check in/out,
    tick a task, file a field report) — the PWA's guest/alias flow carries no
    bearer token, and the plan explicitly lets an anonymous user join and search.
    Write endpoints are rate-limited where they create rows.
  * **Creating / mutating an operation requires a verified account**
    (``require_viewer`` = a real user token, with the dev bypass only while no
    users exist). A coordinator, not a drive-by, defines the operation.
  * **Confirming a ``found`` report is operator-gated** (``require_operator``) so
    an anonymous "found" can't silently flip a public person record — it waits for
    a verified volunteer (plan-26 Phase 6 §3).

Namespaced under ``/sar`` so it never collides with the plan-09 ``/operations``
(events) routes. Every mutation is audit-logged in ``modules/sar.py``.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from auth import current_user, require_role, user_principal
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
    VolunteerRoleUpdate,
)
from modules import sar
from ratelimit import rate_limit

router = APIRouter()

require_viewer = require_role("viewer")
require_operator = require_role("operator")


def _user_id(authorization: Optional[str]) -> Optional[str]:
    user = current_user(authorization)
    return user["id"] if user else None


def _principal(authorization: Optional[str]) -> str:
    """A non-secret audit principal for a (possibly anonymous) volunteer."""
    user = current_user(authorization)
    return user_principal(user) if user else "anon"


# ── Operations (reads public; create/mutate = verified account) ───────────────


@router.get("/sar/operations")
def list_operations(
    disaster_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    return sar.list_operations(disaster_id=disaster_id, status=status)


@router.get("/sar/operations/{op_id}")
def get_operation(op_id: str):
    return sar.get_operation(op_id)


@router.post("/sar/operations", dependencies=[Depends(rate_limit)])
def create_operation(
    req: SarOperationCreate,
    principal: str = Depends(require_viewer),
    authorization: Optional[str] = Header(default=None),
):
    return sar.create_operation(req, actor=principal, user_id=_user_id(authorization))


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


# ── Volunteers + sectors (plan-26 Phase 3, public volunteer actions) ──────────


@router.post("/sar/operations/{op_id}/join", dependencies=[Depends(rate_limit)])
def join_operation(
    op_id: str, req: VolunteerJoin, authorization: Optional[str] = Header(default=None)
):
    return sar.join_operation(
        op_id, req, actor=_principal(authorization), user_id=_user_id(authorization)
    )


@router.post("/sar/sectors/{sector_id}/claim")
def claim_sector(
    sector_id: str, req: SectorClaim, authorization: Optional[str] = Header(default=None)
):
    return sar.claim_sector(sector_id, req, actor=_principal(authorization))


@router.post("/sar/sectors/{sector_id}/release")
def release_sector(sector_id: str, authorization: Optional[str] = Header(default=None)):
    return sar.release_sector(sector_id, actor=_principal(authorization))


@router.patch("/sar/sectors/{sector_id}")
def update_sector(
    sector_id: str, req: SectorStatusUpdate, authorization: Optional[str] = Header(default=None)
):
    return sar.update_sector(sector_id, req, actor=_principal(authorization))


@router.post("/sar/sectors/{sector_id}/checkin")
def checkin_sector(
    sector_id: str, req: VolunteerCheckin, authorization: Optional[str] = Header(default=None)
):
    return sar.checkin_sector(sector_id, req.volunteer_id, actor=_principal(authorization))


@router.post("/sar/volunteers/{volunteer_id}/checkout")
def checkout_volunteer(volunteer_id: str, authorization: Optional[str] = Header(default=None)):
    return sar.checkout_sector(volunteer_id, actor=_principal(authorization))


@router.patch("/sar/volunteers/{volunteer_id}/role")
def change_volunteer_role(
    volunteer_id: str, req: VolunteerRoleUpdate,
    authorization: Optional[str] = Header(default=None),
):
    """Switch a volunteer's role hat (plan-27.5 Phase 3) — a public volunteer
    action like join/check-in; the role only reorders the UI, never gates."""
    return sar.change_volunteer_role(volunteer_id, req.role, actor=_principal(authorization))


# ── Tasks (plan-26 Phase 3, public volunteer actions) ─────────────────────────


@router.post("/sar/operations/{op_id}/tasks")
def add_task(op_id: str, req: SarTaskCreate, authorization: Optional[str] = Header(default=None)):
    return sar.add_task(op_id, req, actor=_principal(authorization))


@router.patch("/sar/tasks/{task_id}")
def update_task(task_id: str, req: SarTaskUpdate, authorization: Optional[str] = Header(default=None)):
    return sar.update_task(task_id, req, actor=_principal(authorization))


@router.delete("/sar/tasks/{task_id}")
def delete_task(task_id: str, authorization: Optional[str] = Header(default=None)):
    return sar.delete_task(task_id, actor=_principal(authorization))


# ── Field reports + mesh/cloud sync (plan-26 Phase 4) ─────────────────────────


@router.get("/sar/operations/{op_id}/field-reports")
def list_field_reports(op_id: str, only_pending: bool = Query(False)):
    return sar.list_field_reports(op_id, only_pending=only_pending)


@router.post("/sar/operations/{op_id}/field-reports", dependencies=[Depends(rate_limit)])
def create_field_report(
    op_id: str, req: FieldReportCreate, authorization: Optional[str] = Header(default=None)
):
    return sar.create_field_report(
        op_id, req, actor=_principal(authorization), user_id=_user_id(authorization)
    )


@router.post("/sar/field-reports/{fr_id}/resolve")
def resolve_field_report(
    fr_id: str, req: FieldReportResolve, principal: str = Depends(require_operator)
):
    """Confirm/dismiss a field report (plan-26 Phase 6) — operator-gated. A
    confirmed ``found`` report applies the registry status update."""
    return sar.resolve_field_report(fr_id, req, actor=principal)


@router.get("/sar/sync")
def sar_sync_download(since: Optional[str] = Query(None)):
    return sar.sync_download(since=since)


@router.post("/sar/sync", dependencies=[Depends(rate_limit)])
def sar_sync_upload(payload: SarSyncPayload):
    return sar.sync_upload(payload)
