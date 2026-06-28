"""Organizations & membership (plan-25 Phase 2).

An organization is a coordinating body (an NGO chapter, a hospital network, a
volunteer collective) whose admins can invite watchers and members. Anyone may
create an org; only an operator/admin can mark one ``verified`` (the flag that
earns the "verified org" badge and lifts member records to the high trust tier —
see modules/trust.py).

`public_key` is pinned at registration (TOFU, like trusted_peers): once set,
changing it requires an explicit operator action so a signed-update key can't be
silently swapped. Membership is (org_id, user_id) with an org-scoped role
(admin|member).
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import now_iso


def _new_id() -> str:
    return "org-" + uuid.uuid4().hex[:12]


def create_org(
    name: str,
    kind: Optional[str] = None,
    description: Optional[str] = None,
    public_key: Optional[str] = None,
    created_by: Optional[str] = None,
    creator_user_id: Optional[str] = None,
) -> dict:
    """Create an org. The creator (``creator_user_id``) is enrolled as its first
    admin so they can immediately invite others."""
    if not (name or "").strip():
        raise HTTPException(status_code=400, detail="name is required")
    now = now_iso()
    org_id = _new_id()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, kind, description, public_key, "
            "verified, created_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
            (org_id, name.strip(), kind, description, public_key, created_by, now, now),
        )
        if creator_user_id:
            conn.execute(
                "INSERT OR IGNORE INTO org_members (org_id, user_id, role, created_at) "
                "VALUES (?, ?, 'admin', ?)",
                (org_id, creator_user_id, now),
            )
        conn.commit()
    return get_org(org_id)


def get_org(org_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        org = db.row_to_dict(row)
        org["members"] = [
            db.row_to_dict(r)
            for r in conn.execute(
                "SELECT org_id, user_id, role, created_at FROM org_members WHERE org_id = ?",
                (org_id,),
            ).fetchall()
        ]
        return org


def list_orgs(verified_only: bool = False) -> List[dict]:
    sql = "SELECT * FROM organizations"
    params: list = []
    if verified_only:
        sql += " WHERE verified = 1"
    sql += " ORDER BY name ASC"
    with db.get_db() as conn:
        return [db.row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def set_verified(org_id: str, verified: bool) -> dict:
    now = now_iso()
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE organizations SET verified = ?, updated_at = ? WHERE id = ?",
            (1 if verified else 0, now, org_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Organization not found")
        conn.commit()
    return get_org(org_id)


def set_public_key(org_id: str, public_key: str) -> dict:
    """Pin/replace the org signing key. TOFU: if a key is already pinned and the
    new one differs, reject with 409 (an operator must clear it deliberately)."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT public_key FROM organizations WHERE id = ?", (org_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        existing = row[0]
        if existing and existing != public_key:
            raise HTTPException(
                status_code=409, detail="A different public key is already pinned"
            )
        conn.execute(
            "UPDATE organizations SET public_key = ?, updated_at = ? WHERE id = ?",
            (public_key, now_iso(), org_id),
        )
        conn.commit()
    return get_org(org_id)


def add_member(org_id: str, user_id: str, role: str = "member") -> dict:
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="role must be admin or member")
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM organizations WHERE id = ?", (org_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Organization not found")
        conn.execute(
            "INSERT INTO org_members (org_id, user_id, role, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(org_id, user_id) DO UPDATE SET role = excluded.role",
            (org_id, user_id, role, now_iso()),
        )
        conn.commit()
    return {"org_id": org_id, "user_id": user_id, "role": role}


def member_role(org_id: str, user_id: str) -> Optional[str]:
    if not (org_id and user_id):
        return None
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT role FROM org_members WHERE org_id = ? AND user_id = ?",
            (org_id, user_id),
        ).fetchone()
        return row[0] if row else None


def is_admin(org_id: str, user_id: str) -> bool:
    return member_role(org_id, user_id) == "admin"
