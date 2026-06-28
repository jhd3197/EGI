"""HTTP adapters for evacuation corridors (plan-21 Phase 6).

Reads (``GET /corridors``) are PUBLIC — a victim's offline map needs the official
recommended evacuation paths before any account exists, like the public shelter,
routing-pack and hazard reads. Writes (``POST /corridors``) are operator-gated and
land trusted (``source='official'``); a corridor is authoritative guidance, not a
crowd report, so there is no community-submission tier here.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_role
from models import CorridorRecord
from modules import audit, corridors
from routes.dependencies import get_or_404

router = APIRouter()


@router.get("/corridors")
def list_corridors(
    disaster_id: Optional[str] = Query(None),
    bbox: Optional[str] = Query(None, description="minLon,minLat,maxLon,maxLat"),
):
    """Public: evacuation corridors (newest first). Optional disaster + bbox."""
    parsed_bbox = None
    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail="bbox must be minLon,minLat,maxLon,maxLat")
        try:
            parsed_bbox = [float(p) for p in parts]
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox values must be numbers")
    return corridors.list_corridors(disaster_id, parsed_bbox)


@router.get("/corridors/{corridor_id}")
def get_corridor(corridor_id: str):
    """Public: a single evacuation corridor by id."""
    return get_or_404(corridors.get_corridor, corridor_id, "Corridor")


@router.post("/corridors")
def create_corridor(
    rec: CorridorRecord,
    operator: str = Depends(require_role("operator")),
):
    """Operator-gated: create/update an official evacuation corridor."""
    result = corridors.upsert_corridor(rec, source="official")
    audit.log_action(operator, "corridor_submit", "corridor", result["id"])
    return result
