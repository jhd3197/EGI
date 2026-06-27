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


@router.post("/duplicates/{cluster_id}/merge")
def merge(cluster_id: str, req: MergeRequest, operator: str = Depends(require_operator)):
    return duplicates.merge_cluster(
        cluster_id, req.canonical_id, req.duplicate_ids, operator=operator
    )


@router.post("/duplicates/{cluster_id}/reject")
def reject(cluster_id: str, operator: str = Depends(require_operator)):
    return duplicates.reject_cluster(cluster_id, operator=operator)
