"""HTTP adapters for the shelter & refugee information hub (plan-20).

Reads (list/detail/updates/family-search) are public — victims and family need
them without an account. Writes split into three tiers:

  * **Check-in** (`POST /shelters/{id}/checkin`) — public + rate-limited; a
    displaced person self-reports without auth.
  * **Feed/capacity writes** — an *operator-or-above* user, OR the shelter's own
    verified operator (a user who claimed it via token). The author role on a
    feed entry is decided here from that auth context, never trusted from the
    client, so an "official" badge always means a verified poster.
  * **Token management** (issue/list/revoke) — commander only.
"""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import (
    ANON_DEV_PRINCIPAL,
    _extract_bearer,
    _match,
    current_user,
    get_operator_tokens,
    require_role,
    token_principal,
    user_principal,
)
from models import (
    ShelterCapacityUpdate,
    ShelterCheckinCreate,
    ShelterClaimRequest,
    ShelterRecord,
    ShelterTokenCreate,
    ShelterUpdateCreate,
)
from models import AnimalRecord
from modules import animals, audit, shelters, users
from ratelimit import rate_limit

router = APIRouter()


def _authorize_writer(shelter_id: str, authorization: Optional[str]) -> dict:
    """Authorize a shelter feed/capacity write.

    Passes for (a) the shelter's own verified operator, (b) any operator+ user,
    (c) a deprecated static operator token, or (d) the dev bypass when no users
    and no tokens exist. Raises 401/403 otherwise. Returns an audit principal +
    the user id (for `author_id`)."""
    user = current_user(authorization)
    if user:
        if shelters.is_operator_of(shelter_id, user["id"]) or users.role_satisfies(
            user["role"], "operator"
        ):
            return {"principal": user_principal(user), "user_id": user["id"]}
        raise HTTPException(status_code=403, detail="Operator or shelter-staff role required")
    token = _extract_bearer(authorization)
    configured = get_operator_tokens()
    if configured:
        if token and _match(token, configured):
            return {"principal": token_principal(token), "user_id": None}
        raise HTTPException(status_code=401, detail="Operator authorization required")
    if users.count_users() == 0:
        return {"principal": ANON_DEV_PRINCIPAL, "user_id": None}
    raise HTTPException(status_code=401, detail="Authentication required")


# ── Shelters ─────────────────────────────────────────────────────────────────


@router.get("/shelters")
def list_shelters(
    disaster_id: Optional[str] = Query(None),
    has_space: bool = Query(False),
    accepts_pets: bool = Query(False),
    has_medical: bool = Query(False),
    needs_supplies: bool = Query(False),
):
    return shelters.list_shelters(
        disaster_id,
        has_space=has_space,
        accepts_pets=accepts_pets,
        has_medical=has_medical,
        needs_supplies=needs_supplies,
    )


@router.get("/shelters/checkins/search")
def search_checkins(alias: str = Query(...)):
    """Public family search: "last seen at <shelter>" for an alias (plan-20 §8)."""
    return shelters.find_checkins_by_alias(alias)


@router.get("/shelters/{shelter_id}")
def get_shelter(shelter_id: str):
    s = shelters.get_shelter(shelter_id)
    if not s:
        raise HTTPException(status_code=404, detail="Shelter not found")
    return s


@router.post("/shelters")
def upsert_shelter(shelter: ShelterRecord, operator: str = Depends(require_role("operator"))):
    result = shelters.upsert_shelter(shelter)
    audit.log_action(operator, "shelter_upsert", "shelter", result["id"])
    return result


@router.patch("/shelters/{shelter_id}/capacity")
def update_capacity(
    shelter_id: str,
    patch: ShelterCapacityUpdate,
    authorization: Optional[str] = Header(default=None),
):
    auth = _authorize_writer(shelter_id, authorization)
    result = shelters.update_capacity(shelter_id, patch)
    if result is None:
        raise HTTPException(status_code=404, detail="Shelter not found")
    audit.log_action(auth["principal"], "shelter_capacity", "shelter", shelter_id)
    return result


# ── Updates feed ─────────────────────────────────────────────────────────────


@router.get("/shelters/{shelter_id}/updates")
def list_updates(shelter_id: str, include_expired: bool = Query(False)):
    return shelters.list_updates(shelter_id, include_expired=include_expired)


@router.post("/shelters/{shelter_id}/updates", dependencies=[Depends(rate_limit)])
def add_update(
    shelter_id: str,
    payload: ShelterUpdateCreate,
    authorization: Optional[str] = Header(default=None),
):
    auth = _authorize_writer(shelter_id, authorization)
    # An authorized writer always posts as 'official' (verified). The client
    # cannot upgrade itself past this.
    result = shelters.add_update(
        shelter_id, payload, author_role="official", author_id=auth["user_id"]
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Shelter not found")
    audit.log_action(auth["principal"], "shelter_update", "shelter", shelter_id)
    return result


# ── Check-ins ────────────────────────────────────────────────────────────────


@router.post("/shelters/{shelter_id}/checkin", dependencies=[Depends(rate_limit)])
def add_checkin(shelter_id: str, payload: ShelterCheckinCreate):
    result = shelters.add_checkin(shelter_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Shelter not found")
    return result


@router.get("/shelters/{shelter_id}/checkins")
def list_checkins(
    shelter_id: str, authorization: Optional[str] = Header(default=None)
):
    _authorize_writer(shelter_id, authorization)  # private list: operator/staff only
    return shelters.list_checkins(shelter_id)


# ── Shelter animal board (plan-28 Phase 4) ───────────────────────────────────
#
# A shelter/clinic lists the animals it is holding so owners can find a lost pet.
# Reads are public; adding an intake requires the shelter's verified operator or
# an operator+ user (same writer gate as the feed/capacity writes).


@router.get("/shelters/{shelter_id}/animals")
def list_shelter_animals(shelter_id: str):
    return animals.list_shelter_animals(shelter_id)


@router.post("/shelters/{shelter_id}/animals", dependencies=[Depends(rate_limit)])
def add_shelter_animal(
    shelter_id: str,
    animal: AnimalRecord,
    authorization: Optional[str] = Header(default=None),
):
    auth = _authorize_writer(shelter_id, authorization)
    if not shelters.get_shelter(shelter_id):
        raise HTTPException(status_code=404, detail="Shelter not found")
    return animals.add_shelter_animal(shelter_id, animal, actor=auth["principal"])


# ── Verified-operator tokens (plan-20 §9) ────────────────────────────────────


@router.post("/shelters/{shelter_id}/tokens")
def issue_token(
    shelter_id: str,
    payload: ShelterTokenCreate,
    commander: str = Depends(require_role("commander")),
):
    result = shelters.issue_token(shelter_id, payload, issued_by=commander)
    if result is None:
        raise HTTPException(status_code=404, detail="Shelter not found")
    audit.log_action(commander, "shelter_token_issue", "shelter", shelter_id)
    return result


@router.get("/shelters/{shelter_id}/tokens")
def list_tokens(shelter_id: str, commander: str = Depends(require_role("commander"))):
    return shelters.list_tokens(shelter_id)


@router.post("/shelters/{shelter_id}/tokens/{token_hint}/revoke")
def revoke_token(
    shelter_id: str,
    token_hint: str,
    commander: str = Depends(require_role("commander")),
):
    if not shelters.revoke_token(token_hint, shelter_id):
        raise HTTPException(status_code=404, detail="Token not found")
    audit.log_action(commander, "shelter_token_revoke", "shelter", shelter_id)
    return {"revoked": True}


@router.post("/shelters/claim")
def claim_shelter(req: ShelterClaimRequest, authorization: Optional[str] = Header(default=None)):
    user = current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = shelters.claim_shelter(req, user)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid, expired, revoked or already-claimed token")
    audit.log_action(user_principal(user), "shelter_claim", "shelter", result["id"])
    return result


# ── Roster export (operator handover) ────────────────────────────────────────


@router.get("/shelters/{shelter_id}/roster.csv")
def roster_csv(shelter_id: str, authorization: Optional[str] = Header(default=None)):
    _authorize_writer(shelter_id, authorization)
    shelter = shelters.get_shelter(shelter_id)
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found")
    rows = shelters.roster(shelter_id)
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM so Excel opens it correctly
    writer = csv.writer(buf)
    writer.writerow(["alias", "note", "person_id", "source", "created_at"])
    for r in rows:
        writer.writerow([
            r.get("alias") or "", r.get("note") or "", r.get("person_id") or "",
            r.get("source") or "", r.get("created_at") or "",
        ])
    buf.seek(0)
    filename = f"roster-{shelter_id}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
