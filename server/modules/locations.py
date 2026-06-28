"""Locations & watcher authorization (plan-25 Phase 2).

A location is a physical place — hospital, shelter, water point, pickup hotspot —
at which a *watcher* can be authorized to confirm/correct information and sign
updates. This is the unit of authorization (who may vouch for data here), distinct
from the public ``shelters`` capacity records.

A watcher is granted by an operator or the owning org's admin, optionally with an
expiry (re-authorization is supported but not forced). An authorized, unexpired,
unrevoked watcher row is what lifts a signed location update to the high trust
tier in modules/trust.py.
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import now_iso


def _new_id() -> str:
    return "loc-" + uuid.uuid4().hex[:12]


def create_location(
    name: str,
    kind: Optional[str] = None,
    org_id: Optional[str] = None,
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    created_by: Optional[str] = None,
) -> dict:
    if not (name or "").strip():
        raise HTTPException(status_code=400, detail="name is required")
    now = now_iso()
    loc_id = _new_id()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO locations (id, org_id, name, kind, address, lat, lon, "
            "created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (loc_id, org_id, name.strip(), kind, address, lat, lon, created_by, now, now),
        )
        conn.commit()
    return get_location(loc_id)


def get_location(location_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Location not found")
        loc = db.row_to_dict(row)
        loc["watchers"] = [
            db.row_to_dict(r)
            for r in conn.execute(
                "SELECT location_id, user_id, authorized_by, expires_at, revoked, created_at "
                "FROM location_watchers WHERE location_id = ? AND revoked = 0",
                (location_id,),
            ).fetchall()
        ]
        return loc


def list_locations(org_id: Optional[str] = None, kind: Optional[str] = None) -> List[dict]:
    sql = "SELECT * FROM locations WHERE 1=1"
    params: list = []
    if org_id:
        sql += " AND org_id = ?"
        params.append(org_id)
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY name ASC"
    with db.get_db() as conn:
        return [db.row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def add_watcher(
    location_id: str,
    user_id: str,
    authorized_by: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> dict:
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM locations WHERE id = ?", (location_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Location not found")
        conn.execute(
            "INSERT INTO location_watchers (location_id, user_id, authorized_by, "
            "expires_at, revoked, created_at) VALUES (?, ?, ?, ?, 0, ?) "
            "ON CONFLICT(location_id, user_id) DO UPDATE SET "
            "authorized_by = excluded.authorized_by, expires_at = excluded.expires_at, "
            "revoked = 0",
            (location_id, user_id, authorized_by, expires_at, now_iso()),
        )
        conn.commit()
    return {"location_id": location_id, "user_id": user_id, "expires_at": expires_at}


def revoke_watcher(location_id: str, user_id: str) -> dict:
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE location_watchers SET revoked = 1 WHERE location_id = ? AND user_id = ?",
            (location_id, user_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Watcher not found")
        conn.commit()
    return {"location_id": location_id, "user_id": user_id, "revoked": True}


def is_active_watcher(location_id: str, user_id: str) -> bool:
    if not (location_id and user_id):
        return False
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT expires_at, revoked FROM location_watchers "
            "WHERE location_id = ? AND user_id = ?",
            (location_id, user_id),
        ).fetchone()
    if not row or row[1]:
        return False
    if row[0] and row[0] < now_iso():
        return False
    return True
