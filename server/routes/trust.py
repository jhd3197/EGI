"""HTTP adapters for the trust layer (plan-25).

Device reputation reads + the device blocklist (Phase 1), and operator ban /
unban controls (Phase 5). The blocklist is what a gateway phone downloads and
spreads through the mesh so offline peers can drop a banned device's records.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from auth import require_role
from modules import audit, device_reputation

router = APIRouter(prefix="/trust")


@router.get("/devices")
def list_devices(
    banned: Optional[bool] = None,
    limit: int = 200,
    operator: str = Depends(require_role("operator")),
):
    """Operator-gated: device reputation rows (optionally only banned ones)."""
    return {"devices": device_reputation.list_devices(banned=banned, limit=limit)}


@router.get("/devices/{device_id}")
def get_device(device_id: str, operator: str = Depends(require_role("operator"))):
    rep = device_reputation.get(device_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Unknown device")
    return rep


@router.get("/blocklist")
def blocklist(operator: str = Depends(require_role("operator"))):
    """The banned-device blocklist bundle (plan-25 §6). A gateway downloads this
    and relays it through the mesh so offline peers ignore banned devices."""
    return {"banned_device_ids": device_reputation.banned_device_ids()}


@router.post("/devices/{device_id}/ban")
def ban_device(
    device_id: str,
    reason: Optional[str] = Body(None, embed=True),
    operator: str = Depends(require_role("commander")),
):
    """Ban a device (commander+). Its records are hidden and future syncs from it
    are rejected. The ban is auditable and propagates via the blocklist bundle."""
    result = device_reputation.set_banned(device_id, True, reason=reason)
    audit.log_action(operator, "device_ban", "device", device_id, detail=reason or "")
    return result


@router.post("/devices/{device_id}/unban")
def unban_device(device_id: str, operator: str = Depends(require_role("commander"))):
    result = device_reputation.set_banned(device_id, False)
    audit.log_action(operator, "device_unban", "device", device_id)
    return result
