"""HTTP adapters for hazard zones (plan-21 Phase 4).

Reads (``GET /hazards``) are public — a victim's offline map needs danger areas
before any account exists, like the public shelter and routing-pack reads. Writes
split into two tiers:

  * **Submit** (``POST /hazards``) — an operator+ user/token submits a TRUSTED
    hazard (``source`` from body or ``official``, reviewed=1). Anyone else may
    submit a community **hazard report** (``source='hazard_report'``, reviewed=0,
    awaiting moderation) — public + rate-limited like a shelter check-in.
  * **Moderation** (``GET /hazards/pending``, ``POST /hazards/{id}/review``) —
    operator-gated; approve/reject a pending report.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from auth import (
    _extract_bearer,
    _match,
    current_user,
    get_operator_tokens,
    require_role,
    token_principal,
    user_principal,
)
from models import HazardRecord, validate_hazard_type
from modules import audit, hazards, users
from ratelimit import rate_limit

router = APIRouter()


def _operator_principal(authorization: Optional[str]) -> Optional[str]:
    """Return an audit principal if the caller is an operator+ user OR a valid
    static operator token, else None. Never raises — a non-operator caller just
    falls through to the community hazard-report path."""
    user = current_user(authorization)
    if user:
        if users.role_satisfies(user["role"], "operator"):
            return user_principal(user)
        return None
    token = _extract_bearer(authorization)
    configured = get_operator_tokens()
    if configured and token and _match(token, configured):
        return token_principal(token)
    return None


@router.get("/hazards")
def list_hazards(
    disaster_id: Optional[str] = Query(None),
    bbox: Optional[str] = Query(None, description="minLon,minLat,maxLon,maxLat"),
    pending: bool = Query(False),
):
    """Public: active, non-rejected hazards (pending crowd reports included,
    flagged via reviewed=0). Optional disaster + bbox filtering."""
    parsed_bbox = None
    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail="bbox must be minLon,minLat,maxLon,maxLat")
        try:
            parsed_bbox = [float(p) for p in parts]
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox values must be numbers")
    return hazards.list_hazards(disaster_id, parsed_bbox, include_pending=pending)


@router.get("/hazards/pending")
def list_pending(operator: str = Depends(require_role("operator"))):
    """Operator-gated: community hazard reports awaiting moderation (reviewed=0)."""
    return hazards.list_pending()


@router.post("/hazards", dependencies=[Depends(rate_limit)])
def submit_hazard(hazard: HazardRecord, authorization: Optional[str] = Header(default=None)):
    if not validate_hazard_type(hazard.type):
        raise HTTPException(status_code=400, detail="Invalid hazard type")
    principal = _operator_principal(authorization)
    if principal:
        # Trusted submission: operator-chosen source (default 'official'), approved.
        source = hazard.source if hazard.source in {"web", "official", "hazard_report"} else "official"
        if source == "web":
            source = "official"
        result = hazards.upsert_hazard(hazard, source=source, reviewed=1)
        audit.log_action(principal, "hazard_submit", "hazard", result["id"])
    else:
        # Community report: untrusted, awaits moderation.
        result = hazards.upsert_hazard(hazard, source="hazard_report", reviewed=0)
    return result


@router.post("/hazards/{hazard_id}/review")
def review_hazard(
    hazard_id: str,
    approve: bool = Body(..., embed=True),
    operator: str = Depends(require_role("operator")),
):
    result = hazards.review_hazard(hazard_id, approve)
    if result is None:
        raise HTTPException(status_code=404, detail="Hazard not found")
    audit.log_action(
        operator, "hazard_approve" if approve else "hazard_reject", "hazard", hazard_id
    )
    return result
