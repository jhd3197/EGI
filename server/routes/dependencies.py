"""Shared FastAPI route helpers — thin adapters reused across routers.

Routes repeat a handful of tiny patterns: fetch-or-404, parse a ``bbox`` query,
clamp a pagination limit. Centralizing them keeps the routers thin and the 404
messages/limits consistent. These are deliberately plain helpers (not magic) so a
router reads the same as before, just without the copy-paste.
"""

from typing import Callable, List, Optional

from fastapi import HTTPException, Query


def get_or_404(fetch: Callable[[str], Optional[dict]], record_id: str,
               label: str = "Record"):
    """Return ``fetch(record_id)`` or raise a 404 with ``"{label} not found"``.

    Collapses the ``x = mod.get(id); if not x: raise HTTPException(404, ...)``
    block repeated ~30 times across the route layer.
    """
    record = fetch(record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


def parse_bbox(bbox: Optional[str] = Query(default=None)) -> Optional[List[float]]:
    """Parse a ``minLon,minLat,maxLon,maxLat`` query into four floats.

    Returns ``None`` when unset; raises 400 on a malformed value. Usable directly
    as a dependency: ``bbox: Optional[list[float]] = Depends(parse_bbox)``.
    """
    if not bbox:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be 'minLon,minLat,maxLon,maxLat'")
    try:
        return [float(p) for p in parts]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bbox values must be numbers")
