"""Routes for the moderation queue."""

from fastapi import APIRouter, Depends

from auth import require_operator
from modules import audit, moderation

router = APIRouter(prefix="/moderation")


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
