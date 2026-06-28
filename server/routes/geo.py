"""Geospatial routes: nearby person lookup + per-operation map data (plan-10).

Thin HTTP adapters over ``modules.geo``. ``GET /persons/nearby`` is public to
match ``GET /persons``; the operation map endpoints are viewer-gated like the
rest of the operations surface.

NOTE: ``/persons/nearby`` collides with ``/persons/{person_id}`` in
routes/persons.py — this router MUST be included BEFORE the persons router in
main.py so the literal ``nearby`` path wins over the path parameter.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_viewer
from modules import geo

router = APIRouter()


@router.get("/persons/nearby")
def nearby_persons(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(1000),
    limit: int = Query(200, ge=1, le=1000),
):
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="lat/lon out of range")
    return geo.nearby_persons(lat, lon, radius_m, limit=limit)


@router.get("/operations/{op_id}/heatmap")
def operation_heatmap(op_id: str, principal: str = Depends(require_viewer)):
    return geo.operation_heatmap(op_id)


@router.get("/operations/{op_id}/bounds")
def operation_bounds(op_id: str, principal: str = Depends(require_viewer)):
    return geo.operation_bounds(op_id)


@router.get("/operations/{op_id}/sectors")
def operation_sectors(
    op_id: str,
    top: int = Query(5, ge=1, le=50),
    cell_deg: Optional[float] = Query(None, gt=0),
    principal: str = Depends(require_viewer),
):
    """Suggested search sectors by report/person density (plan-13 hot zones)."""
    return geo.suggested_sectors(op_id, top=top, cell_deg=cell_deg)
