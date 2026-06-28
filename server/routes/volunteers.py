"""HTTP adapters for the volunteer registry (plan-27.5 Phase 1).

Access model:
  * **Register / read / update your own profile is public** — the PWA's guest
    flow carries no bearer token, and the plan explicitly lets anyone register to
    help (keyed by ``device_id`` when there is no account). Writes are
    rate-limited. A logged-in user's profile is keyed by their account instead.
  * **Discovery (``/volunteers/nearby``) is public** but only returns
    ``visible=1`` profiles — a coordinator (or anyone) can find available helpers
    near an operation. The registry deliberately exposes only what the volunteer
    chose to make discoverable.

Higher-trust volunteer roles (remote watcher, facility watcher, coordinator) are
gated by Plan 25 verification at the point of *action*, not at registration —
registering a profile is intentionally low-friction (plan-27.5 §5).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from auth import current_user, user_principal
from models import VolunteerProfileWrite
from modules import volunteers
from ratelimit import rate_limit

router = APIRouter()


def _user_id(authorization: Optional[str]) -> Optional[str]:
    user = current_user(authorization)
    return user["id"] if user else None


def _principal(authorization: Optional[str]) -> str:
    user = current_user(authorization)
    return user_principal(user) if user else "anon"


@router.post("/volunteers/register", dependencies=[Depends(rate_limit)])
def register(
    req: VolunteerProfileWrite, authorization: Optional[str] = Header(default=None)
):
    return volunteers.register_profile(
        req, actor=_principal(authorization), user_id=_user_id(authorization)
    )


@router.get("/volunteers/me")
def get_me(
    device_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(default=None),
):
    return volunteers.get_me(_user_id(authorization), device_id)


@router.patch("/volunteers/me", dependencies=[Depends(rate_limit)])
def patch_me(
    req: VolunteerProfileWrite,
    device_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(default=None),
):
    return volunteers.update_me(
        req, _user_id(authorization), device_id or req.device_id,
        actor=_principal(authorization),
    )


@router.get("/volunteers/nearby")
def nearby(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_m: float = Query(25000),
    op_id: Optional[str] = Query(None),
    availability: Optional[str] = Query("available"),
    skill: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    return volunteers.nearby(
        lat=lat, lon=lon, radius_m=radius_m, op_id=op_id,
        availability=availability, skill=skill, limit=limit,
    )


@router.get("/volunteers/sync")
def sync_download(since: Optional[str] = Query(None)):
    return volunteers.sync_download(since=since)
