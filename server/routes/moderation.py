"""Routes for the moderation queue."""

from fastapi import APIRouter

from modules import moderation

router = APIRouter(prefix="/moderation")


@router.get("/pending")
def pending():
    return moderation.list_pending()


@router.get("/stats")
def stats():
    return moderation.stats()


@router.post("/{record_id}/approve")
def approve(record_id: str):
    return moderation.approve(record_id)


@router.post("/{record_id}/reject")
def reject(record_id: str):
    return moderation.reject(record_id)
