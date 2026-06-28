"""HTTP adapters for offline routing packs (plan-21, Phase 2).

All three endpoints are PUBLIC and unauthenticated: a victim needs to download a
routing pack offline-first, before any account exists, exactly like map tiles
and the public shelter reads. The server only serves metadata + the static graph
JSON; the A* pathfinding runs entirely on the client.
"""

from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from modules import routing
from routes.dependencies import get_or_404

router = APIRouter()


@router.get("/routing/packs")
def list_packs(region: Optional[str] = Query(None)):
    """List available routing packs (metadata only), optionally by region."""
    return {"records": routing.list_packs(region)}


@router.get("/routing/packs/{pack_id}/meta")
def pack_meta(pack_id: str):
    """Metadata for one pack (no graph payload)."""
    return get_or_404(routing.get_pack_meta, pack_id, "Routing pack")


@router.get("/routing/packs/{pack_id}")
def get_pack(pack_id: str):
    """Return the full graph JSON for a pack (the downloadable road network)."""
    path = get_or_404(routing.get_pack_path, pack_id, "Routing pack")
    return FileResponse(path, media_type="application/json")
