"""Data-quality scoring routes (plan-13 §4).

Read endpoints (per-record score, low-quality list, stale list, summary) are
viewer-gated; recalculation mutates the cache and is operator-gated. Scores are a
recomputable cache over ``persons`` — see ``modules.quality``.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_operator, require_role
from modules import quality

router = APIRouter()

require_viewer = require_role("viewer")


@router.get("/quality/summary")
def quality_summary(principal: str = Depends(require_viewer)):
    return quality.summary()


@router.get("/quality/low")
def low_quality(
    threshold: int = Query(50, ge=0, le=100),
    limit: int = Query(100, ge=1, le=1000),
    principal: str = Depends(require_viewer),
):
    return quality.low_quality(threshold=threshold, limit=limit)


@router.get("/quality/stale")
def stale_records(
    days: int = Query(quality.STALE_DAYS, ge=1),
    limit: int = Query(200, ge=1, le=1000),
    principal: str = Depends(require_viewer),
):
    return quality.stale_records(days=days, limit=limit)


@router.get("/quality/persons/{person_id}")
def person_score(person_id: str, principal: str = Depends(require_viewer)):
    cached = quality.get_score(person_id)
    if cached is None:
        # Compute on demand the first time (and cache it).
        return quality.score_person(person_id)
    return cached


@router.post("/quality/persons/{person_id}/recalculate")
def recalculate_person(person_id: str, operator: str = Depends(require_operator)):
    return quality.score_person(person_id)


@router.post("/quality/recalculate")
def recalculate_all(operator: str = Depends(require_operator)):
    return quality.recalculate_all()
