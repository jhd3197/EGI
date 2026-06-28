"""HTTP adapters for organizations, membership & invites (plan-25 Phase 2).

Management is operator-gated (the OrgAdminScreen surface); a light public list of
verified orgs lets the PWA render the "verified org" badge. Invite redemption is
bound to a real user account.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header

from auth import current_user, require_role, require_user
from models import InviteCreate, InviteRedeem, OrgCreate, OrgKeyPin, OrgMemberAdd
from modules import audit, invites, organizations

router = APIRouter(prefix="/orgs")


def _principal_user_id(authorization: Optional[str]) -> Optional[str]:
    user = current_user(authorization)
    return user["id"] if user else None


@router.get("")
def list_orgs(all: bool = False, operator: str = Depends(require_role("viewer"))):
    """Verified orgs by default (for badges); ``?all=true`` lists every org."""
    return {"orgs": organizations.list_orgs(verified_only=not all)}


@router.post("")
def create_org(
    body: OrgCreate,
    operator: str = Depends(require_role("operator")),
    authorization: Optional[str] = Header(default=None),
):
    org = organizations.create_org(
        name=body.name,
        kind=body.kind,
        description=body.description,
        public_key=body.public_key,
        created_by=operator,
        creator_user_id=_principal_user_id(authorization),
    )
    audit.log_action(operator, "org_create", "org", org["id"], detail=body.name)
    return org


@router.get("/{org_id}")
def get_org(org_id: str, operator: str = Depends(require_role("operator"))):
    return organizations.get_org(org_id)


@router.post("/{org_id}/verify")
def verify_org(
    org_id: str, verified: bool = True, operator: str = Depends(require_role("admin"))
):
    """Admin-only: mark an org verified (lifts its members to high trust)."""
    org = organizations.set_verified(org_id, verified)
    audit.log_action(
        operator, "org_verify" if verified else "org_unverify", "org", org_id
    )
    return org


@router.post("/{org_id}/key")
def pin_key(org_id: str, body: OrgKeyPin, operator: str = Depends(require_role("operator"))):
    """Pin the org signing key (TOFU; 409 if a different key is already pinned)."""
    org = organizations.set_public_key(org_id, body.public_key)
    audit.log_action(operator, "org_key_pin", "org", org_id)
    return org


@router.post("/{org_id}/members")
def add_member(
    org_id: str, body: OrgMemberAdd, operator: str = Depends(require_role("operator"))
):
    res = organizations.add_member(org_id, body.user_id, role=body.role or "member")
    audit.log_action(operator, "org_member_add", "org", org_id, detail=body.user_id)
    return res


@router.post("/{org_id}/invites")
def create_invite(
    org_id: str, body: InviteCreate, operator: str = Depends(require_role("operator"))
):
    """Mint an org invite (link/QR). The raw token is returned ONCE."""
    res = invites.create_invite(
        "org", org_id, grant_role=body.grant_role, label=body.label,
        issued_by=operator, expires_at=body.expires_at,
    )
    audit.log_action(operator, "org_invite_create", "org", org_id)
    return res


# Invite redemption lives under /trust so a single endpoint handles both org and
# location invites (the token carries its own target).
redeem_router = APIRouter(prefix="/trust")


@redeem_router.post("/invites/redeem")
def redeem_invite(body: InviteRedeem, user: dict = Depends(require_user)):
    """Claim an org/location invite as the logged-in user."""
    res = invites.redeem_invite(body.token, user["id"])
    audit.log_action(
        f"user:{user['id']}", "invite_redeem", res["target_type"], res["target_id"]
    )
    return res
