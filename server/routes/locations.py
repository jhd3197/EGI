"""HTTP adapters for authorization locations & watchers (plan-25 Phase 2).

Reads are public (a victim's map can show authorized locations); watcher
authorization + invites are operator-gated. A watcher invite issued here is the
"scan a location QR code to become a watcher" flow from the plan.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import require_role
from models import InviteCreate, LocationCreate, WatcherAdd
from modules import audit, invites, locations

router = APIRouter(prefix="/locations")


@router.get("")
def list_locations(
    org_id: Optional[str] = Query(None), kind: Optional[str] = Query(None)
):
    """Public: authorization locations (hospital/shelter/water point/pickup)."""
    return {"locations": locations.list_locations(org_id=org_id, kind=kind)}


@router.get("/{location_id}")
def get_location(location_id: str):
    """Public: one location (includes its active watcher count, not identities)."""
    loc = locations.get_location(location_id)
    # Don't leak watcher user ids publicly — expose only the count.
    loc["watcher_count"] = len(loc.pop("watchers", []))
    return loc


@router.post("")
def create_location(body: LocationCreate, operator: str = Depends(require_role("operator"))):
    loc = locations.create_location(
        name=body.name, kind=body.kind, org_id=body.org_id, address=body.address,
        lat=body.lat, lon=body.lon, created_by=operator,
    )
    audit.log_action(operator, "location_create", "location", loc["id"], detail=body.name)
    return loc


@router.get("/{location_id}/watchers")
def list_watchers(location_id: str, operator: str = Depends(require_role("operator"))):
    """Operator-gated: the watcher identities for a location."""
    return {"watchers": locations.get_location(location_id).get("watchers", [])}


@router.post("/{location_id}/watchers")
def add_watcher(
    location_id: str, body: WatcherAdd, operator: str = Depends(require_role("operator"))
):
    res = locations.add_watcher(
        location_id, body.user_id, authorized_by=operator, expires_at=body.expires_at
    )
    audit.log_action(operator, "watcher_add", "location", location_id, detail=body.user_id)
    return res


@router.post("/{location_id}/watchers/{user_id}/revoke")
def revoke_watcher(
    location_id: str, user_id: str, operator: str = Depends(require_role("operator"))
):
    res = locations.revoke_watcher(location_id, user_id)
    audit.log_action(operator, "watcher_revoke", "location", location_id, detail=user_id)
    return res


@router.post("/{location_id}/invites")
def create_invite(
    location_id: str, body: InviteCreate, operator: str = Depends(require_role("operator"))
):
    """Mint a watcher invite for this location (the location-QR flow). Token once."""
    res = invites.create_invite(
        "location", location_id, label=body.label, issued_by=operator,
        expires_at=body.expires_at,
    )
    audit.log_action(operator, "location_invite_create", "location", location_id)
    return res
