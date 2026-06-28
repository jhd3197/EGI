"""HTTP adapters for the missing-animals (pets) registry (plan-28).

Animals are a parallel track to persons. Reads are public (families search for a
lost pet without an account); creating/updating a report is public + rate-limited
like a person report (plan-28 §4: a lower verification bar than missing persons).
Moderation of animal records reuses the persons moderation machinery via the
shared ``reviewed`` flag, so there is no animal-specific approve/reject route here.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from models import AnimalRecord
from modules import animals
from ratelimit import rate_limit

router = APIRouter()


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
