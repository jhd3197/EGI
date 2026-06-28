"""Routes for the fuzzy-dedup moderator queue: list / merge / reject clusters."""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_operator
from modules import duplicates

router = APIRouter()


class MergeRequest(BaseModel):
    canonical_id: str
    duplicate_ids: Optional[List[str]] = None


@router.get("/duplicates/pending")
def pending():
    return duplicates.pending_clusters()


@router.get("/duplicates/exact")
def exact():
    """Exact-match clusters only (same cédula or phone+name) — high confidence."""
    return duplicates.exact_pending()


@router.post("/duplicates/auto-merge-exact")
def auto_merge_exact(dry_run: bool = False, operator: str = Depends(require_operator)):
    """Auto-merge every exact-match cluster (operator-gated). ``dry_run=true`` previews."""
    return duplicates.auto_merge_exact(operator=operator, dry_run=dry_run)


@router.post("/duplicates/{cluster_id}/merge")
def merge(cluster_id: str, req: MergeRequest, operator: str = Depends(require_operator)):
    return duplicates.merge_cluster(
        cluster_id, req.canonical_id, req.duplicate_ids, operator=operator
    )


@router.post("/duplicates/{cluster_id}/reject")
def reject(cluster_id: str, operator: str = Depends(require_operator)):
    return duplicates.reject_cluster(cluster_id, operator=operator)
