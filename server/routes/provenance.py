"""Raw-source provenance read API (plan-24.5).

Operator-gated endpoints that let a moderator trace a record back to the raw
file it came from, including the original filename, SHA-256 hash, extraction
method, and other records from the same batch.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_operator
from modules import provenance

router = APIRouter()


@router.get("/provenance/persons/{person_id}")
def get_person_provenance(person_id: str, operator: str = Depends(require_operator)):
    """Return a person plus its import batch and change history."""
    result = provenance.get_person_provenance(person_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@router.get("/provenance/batches/{batch_id}")
def get_batch(batch_id: str, operator: str = Depends(require_operator)):
    """Return a batch plus all persons and reports linked to it."""
    result = provenance.get_batch_provenance(batch_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return result


@router.get("/provenance/batches")
def list_batches(
    disaster_id: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    operator: str = Depends(require_operator),
):
    """List import batches with optional filters."""
    return provenance.list_batches(
        disaster_id=disaster_id,
        source_type=source_type,
        status=status,
        limit=limit,
        offset=offset,
    )
