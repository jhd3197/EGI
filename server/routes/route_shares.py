"""HTTP adapters for shareable routes (plan-21 Phase 5).

A route share is a victim/responder broadcasting "here is a usable path from A to
B" so others can reuse it. Reads and writes are both PUBLIC and alias-only (like a
shelter check-in): no account is required, because the people who most need to
share a safe path during a disaster won't have one. Writes are rate-limited, and
the server collapses near-identical re-shares server-side (see
``modules.route_shares.share_route``) so the open write surface can't be flooded
with duplicates.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models import RouteShareRecord
from modules import route_shares
from ratelimit import rate_limit
from routes.dependencies import get_or_404

router = APIRouter()


@router.post("/routes/share", dependencies=[Depends(rate_limit)])
def share_route(rec: RouteShareRecord):
    """Public: share a route. Returns the (possibly deduped) stored record."""
    source = rec.source if rec.source in {"web", "android", "mesh"} else "web"
    return route_shares.share_route(rec, source=source)


@router.get("/routes/shared")
def list_shared(
    disaster_id: Optional[str] = Query(None),
    bbox: Optional[str] = Query(None, description="minLon,minLat,maxLon,maxLat"),
    limit: int = Query(100, ge=1, le=500),
):
    """Public: shared routes (newest first). Optional disaster + bbox filtering."""
    parsed_bbox = None
    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail="bbox must be minLon,minLat,maxLon,maxLat")
        try:
            parsed_bbox = [float(p) for p in parts]
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox values must be numbers")
    return route_shares.list_shared(disaster_id, parsed_bbox, limit=limit)


@router.get("/routes/shared/{share_id}")
def get_shared(share_id: str):
    """Public: a single shared route by id."""
    return get_or_404(route_shares.get_route_share, share_id, "Route share")
