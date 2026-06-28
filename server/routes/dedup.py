"""Routes for the persisted merge-candidate review queue (plan-27 Phases 2-4).

The on-the-fly fuzzy clusters live under ``/duplicates``; these endpoints expose
the *scored, persisted* candidates a moderator works through one pair at a time,
with the conflict-resolution preview attached. Merges still flow through the
audited soft-merge primitive, so provenance/history/webhooks are preserved.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_operator
from modules import dedup

router = APIRouter()


class CandidateDecision(BaseModel):
    decision: str                       # 'merge' | 'not_match' | 'needs_info'
    canonical_id: Optional[str] = None
    note: Optional[str] = None


@router.get("/merge-candidates")
def list_candidates(status: str = "pending", limit: int = 200):
    """List persisted merge candidates (default: pending), highest confidence first."""
    return dedup.list_candidates(status=status, limit=limit)


@router.get("/merge-candidates/{candidate_id}")
def get_candidate(candidate_id: str):
    return dedup.get_candidate(candidate_id)


@router.post("/merge-candidates/scan")
def scan(operator: str = Depends(require_operator)):
    """Recompute the fuzzy merge-candidate queue over the whole registry."""
    return dedup.generate_candidates()


@router.post("/merge-candidates/{candidate_id}/resolve")
def resolve(candidate_id: str, req: CandidateDecision,
            operator: str = Depends(require_operator)):
    """Apply a reviewer decision: merge / not_match / needs_info."""
    return dedup.resolve_candidate(
        candidate_id, req.decision, canonical_id=req.canonical_id,
        note=req.note, operator=operator,
    )
