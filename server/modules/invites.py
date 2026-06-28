"""One-time trust invites (plan-25 Phase 2).

An admin issues an invite that grants an org membership or a location watcher
badge when redeemed. Delivered as an invite link or a QR code. Like user_tokens
and shelter_tokens, only ``SHA-256(token)`` is stored — the raw token is shown
once at issuance and never again.

Redemption is bound to a real user account (you must be logged in to claim a
badge), so the granted membership/watcher row links to a concrete user id.
"""

import uuid
from typing import Optional

from fastapi import HTTPException

import db
from models import now_iso
from modules.users import generate_token, hash_token


def create_invite(
    target_type: str,
    target_id: str,
    grant_role: Optional[str] = None,
    label: Optional[str] = None,
    issued_by: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> dict:
    """Mint an invite. Returns the raw token (shown ONCE) + a relative claim URL
    suitable for a QR code. ``target_type`` is 'org' or 'location'."""
    if target_type not in ("org", "location"):
        raise HTTPException(status_code=400, detail="target_type must be org or location")
    # Validate the target exists so we don't mint dangling invites.
    table = "organizations" if target_type == "org" else "locations"
    with db.get_db() as conn:
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (target_id,)).fetchone():
            raise HTTPException(status_code=404, detail=f"{target_type} not found")
    if target_type == "org":
        grant_role = grant_role if grant_role in ("admin", "member") else "member"
    else:
        grant_role = "watcher"

    raw = generate_token()
    token_hash = hash_token(raw)
    now = now_iso()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO trust_invites (token_hash, target_type, target_id, grant_role, "
            "label, issued_by, revoked, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (token_hash, target_type, target_id, grant_role, label, issued_by, expires_at, now),
        )
        conn.commit()
    return {
        "token": raw,  # shown once
        "claim_url": f"/trust/invite?token={raw}",
        "target_type": target_type,
        "target_id": target_id,
        "grant_role": grant_role,
        "expires_at": expires_at,
    }


def redeem_invite(token: str, user_id: str) -> dict:
    """Claim an invite as ``user_id``: grants the org membership or location
    watcher badge. Single-use; marks the invite claimed. Never reveals whether a
    bad token was malformed vs. expired vs. used — all 404."""
    from modules import locations, organizations

    if not (token or "").strip():
        raise HTTPException(status_code=400, detail="token is required")
    token_hash = hash_token(token.strip())
    now = now_iso()
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT target_type, target_id, grant_role, revoked, claimed_at, expires_at "
            "FROM trust_invites WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invalid or expired invite")
        target_type, target_id, grant_role, revoked, claimed_at, expires_at = row
        if revoked or claimed_at or (expires_at and expires_at < now):
            raise HTTPException(status_code=404, detail="Invalid or expired invite")
        conn.execute(
            "UPDATE trust_invites SET claimed_by_user_id = ?, claimed_at = ? WHERE token_hash = ?",
            (user_id, now, token_hash),
        )
        conn.commit()

    if target_type == "org":
        organizations.add_member(target_id, user_id, role=grant_role or "member")
    else:
        locations.add_watcher(target_id, user_id, authorized_by="invite")
    return {
        "ok": True,
        "target_type": target_type,
        "target_id": target_id,
        "grant_role": grant_role,
    }


def revoke_invite(token_hash: str) -> dict:
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE trust_invites SET revoked = 1 WHERE token_hash = ?", (token_hash,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Invite not found")
        conn.commit()
    return {"ok": True, "token_hash": token_hash}
