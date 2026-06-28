"""Routes for the moderation queue + flags (plan-25 Phase 3)."""

from fastapi import APIRouter, Depends

from auth import require_operator
from models import FlagCreate, FlagResolve
from modules import audit, moderation
from ratelimit import rate_limit

router = APIRouter(prefix="/moderation")

# Flags get their own short prefix so "Reportar información incorrecta" (Phase 4)
# is one obvious POST /flags from any record. Creation is public + rate-limited
# (a victim flagging a wrong record has no account); review is operator-gated.
flags_router = APIRouter(prefix="/flags")


@flags_router.post("", dependencies=[Depends(rate_limit)])
def create_flag(body: FlagCreate):
    """Public: report a concern about a record. Offline clients queue and POST
    this later, so it doubles as the flag-sync endpoint."""
    return moderation.create_flag(
        record_type=body.record_type,
        record_id=body.record_id,
        flag_reason=body.flag_reason,
        note=body.note,
        flagged_by=body.flagged_by,
        origin_device=body.origin_device,
    )


@flags_router.get("")
def list_flags(
    status: str = "open",
    record_type: str = None,
    operator: str = Depends(require_operator),
):
    return moderation.list_flags(status=status, record_type=record_type)


@flags_router.get("/stats")
def flag_stats(operator: str = Depends(require_operator)):
    return moderation.flag_stats()


@flags_router.post("/{flag_id}/resolve")
def resolve_flag(
    flag_id: str, body: FlagResolve, operator: str = Depends(require_operator)
):
    return moderation.resolve_flag(
        flag_id, status=body.status, resolution=body.resolution, reviewed_by=operator
    )


@router.get("/pending")
def pending():
    return moderation.list_pending()


@router.get("/stats")
def stats():
    return moderation.stats()


@router.get("/audit")
def audit_log(limit: int = 100, operator: str = Depends(require_operator)):
    """Recent operator actions and auth events (operator-only — may name actors)."""
    return {"actions": audit.list_actions(limit)}


@router.get("/history/{person_id}")
def record_history(person_id: str, operator: str = Depends(require_operator)):
    """Append-only change trail for one person record (operator-only)."""
    return {"history": audit.list_history(person_id)}


@router.post("/{record_id}/approve")
def approve(record_id: str, operator: str = Depends(require_operator)):
    return moderation.approve(record_id, operator=operator)


@router.post("/{record_id}/reject")
def reject(record_id: str, operator: str = Depends(require_operator)):
    return moderation.reject(record_id, operator=operator)
