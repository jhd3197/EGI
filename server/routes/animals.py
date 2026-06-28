"""HTTP adapters for the missing-animals (pets) registry (plan-28).

Animals are a parallel track to persons. Reads are public (families search for a
lost pet without an account); creating/updating a report is public + rate-limited
like a person report (plan-28 §4: a lower verification bar than missing persons).
Moderation of animal records reuses the persons moderation machinery via the
shared ``reviewed`` flag, so there is no animal-specific approve/reject route here.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from auth import require_role
from models import AnimalRecord
from modules import animals, animals_dedup
from ratelimit import rate_limit

router = APIRouter()


# ── Deduplication (plan-28 Phase 5, operator-gated) ──────────────────────────
# Declared before the dynamic GET /animals/{id} so the literal /animals/duplicates
# path isn't shadowed by the {animal_id} matcher.


@router.get("/animals/duplicates")
def list_animal_duplicates(
    disaster_id: Optional[str] = Query(None),
    min_confidence: float = Query(animals_dedup.MEDIUM_THRESHOLD, ge=0.0, le=1.0),
    operator: str = Depends(require_role("operator")),
):
    return animals_dedup.find_candidates(disaster_id, min_confidence=min_confidence)


@router.post("/animals/duplicates/auto-merge-exact")
def auto_merge_exact_animals(
    disaster_id: Optional[str] = Query(None),
    operator: str = Depends(require_role("operator")),
):
    return animals_dedup.auto_merge_exact(disaster_id, operator=operator)


@router.post("/animals/duplicates/merge")
def merge_animals(
    canonical_id: str = Body(..., embed=True),
    duplicate_id: str = Body(..., embed=True),
    operator: str = Depends(require_role("operator")),
):
    return animals_dedup.merge_animals(canonical_id, duplicate_id, operator=operator)


@router.post("/animals/duplicates/reject")
def reject_animal_pair(
    a_id: str = Body(..., embed=True),
    b_id: str = Body(..., embed=True),
    operator: str = Depends(require_role("operator")),
):
    return animals_dedup.reject_pair(a_id, b_id, operator=operator)


@router.get("/animals")
def list_animals(
    disaster_id: Optional[str] = Query(None),
    species: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    shelter_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    return animals.list_animals(
        disaster_id,
        species=species,
        status=status,
        location=location,
        shelter_id=shelter_id,
        limit=limit,
    )


@router.get("/animals/{animal_id}")
def get_animal(animal_id: str):
    from fastapi import HTTPException

    a = animals.get_animal(animal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Animal not found")
    return a


@router.post("/animals", dependencies=[Depends(rate_limit)])
def create_animal(animal: AnimalRecord):
    return animals.upsert_animal(animal)


@router.patch("/animals/{animal_id}/status", dependencies=[Depends(rate_limit)])
def update_status(animal_id: str, payload: AnimalRecord):
    # Only the status field is honored here; the rest of the body is ignored so a
    # status change can't silently overwrite other fields.
    return animals.set_status(animal_id, payload.status)


@router.post("/animals/{animal_id}/contact", dependencies=[Depends(rate_limit)])
def reveal_contact(animal_id: str):
    """Reveal an owner's contact for one animal (plan-28 Phase 6). Rate-limited and
    one-at-a-time so the public list can't be bulk-scraped for phone numbers."""
    from fastapi import HTTPException

    result = animals.reveal_contact(animal_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Animal not found")
    return result
