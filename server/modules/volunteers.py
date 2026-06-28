"""Volunteer registry (plan-27.5 Phase 1).

A lightweight, OPTIONAL profile for people who want to help. It does not replace
the anonymous join path: a volunteer can still enroll in an operation
(``modules.sar.join_operation``) with no profile at all. A profile makes the
volunteer *discoverable* — coordinators can find available helpers near an
operation and invite them.

Conventions reused from the rest of the server:
  * Identity is the user id when there is an account, else the device id (the
    PWA's guest flow). One profile per identity — re-registering updates it.
  * ``languages``/``skills`` are JSON-array TEXT columns, decoded here so clients
    see lists.
  * Upserts are timestamp-guarded last-write-wins on ``id`` (same model as
    ``/sync``) so offline/mesh copies merge cleanly.
  * Mutating helpers audit-log via ``modules.audit``.
"""

import json
import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import VolunteerProfileWrite, now_iso, normalize_ts
from modules.geo import haversine_m


def _new_id() -> str:
    return f"vp-{uuid.uuid4().hex[:10]}"


def _audit(actor: str, action: str, profile_id: str, detail: str = "") -> None:
    from modules import audit

    audit.log_action(actor, action, "volunteer_profile", profile_id, detail=detail)


def _decode(row) -> dict:
    """Row → dict with JSON list columns decoded and ``visible`` as a bool."""
    d = db.row_to_dict(row)
    for col in ("languages", "skills"):
        raw = d.get(col)
        if raw:
            try:
                d[col] = json.loads(raw)
            except (TypeError, ValueError):
                d[col] = []
        else:
            d[col] = []
    d["visible"] = bool(d.get("visible"))
    return d


def _find_existing(conn, user_id: Optional[str], device_id: Optional[str], profile_id: Optional[str]):
    if profile_id:
        row = conn.execute(
            "SELECT * FROM volunteer_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if row:
            return row
    if user_id:
        row = conn.execute(
            "SELECT * FROM volunteer_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return row
    if device_id:
        row = conn.execute(
            "SELECT * FROM volunteer_profiles WHERE device_id = ? AND user_id IS NULL",
            (device_id,),
        ).fetchone()
        if row:
            return row
    return None


def register_profile(
    data: VolunteerProfileWrite, actor: str = "anon",
    user_id: Optional[str] = None,
) -> dict:
    """Create or update the caller's volunteer profile (idempotent per identity).

    Re-registering with the same identity (user id, else device id) refreshes the
    existing row rather than duplicating it. Timestamp-guarded LWW on ``id`` so a
    re-synced create can't clobber a newer update.
    """
    now = now_iso()
    device_id = data.device_id
    if not user_id and not device_id:
        raise HTTPException(status_code=400, detail="user account or device_id required")
    with db.get_db() as conn:
        existing = _find_existing(conn, user_id, device_id, data.id)
        if existing:
            return _update_row(conn, existing, data, now, actor)
        pid = data.id or _new_id()
        created_at = normalize_ts(data.createdAt or now)
        updated_at = normalize_ts(data.updatedAt or now)
        conn.execute(
            """
            INSERT INTO volunteer_profiles
            (id, user_id, device_id, display_name, contact, region, lat, lon,
             languages, skills, availability, mobility, visible, notes,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                pid, user_id, device_id, data.display_name, data.contact, data.region,
                data.lat, data.lon,
                json.dumps(data.languages) if data.languages is not None else None,
                json.dumps(data.skills) if data.skills is not None else None,
                data.availability or "available", data.mobility or "local",
                1 if data.visible is None else (1 if data.visible else 0),
                data.notes, created_at, updated_at,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM volunteer_profiles WHERE id = ?", (pid,)).fetchone()
    _audit(actor, "volunteer_register", pid, f"availability={data.availability or 'available'}")
    return _decode(row)


def _update_row(conn, existing, data: VolunteerProfileWrite, now: str, actor: str) -> dict:
    """Apply a partial update to an existing profile row (LWW guarded)."""
    pid = existing["id"]
    incoming = normalize_ts(data.updatedAt or now)
    stored = normalize_ts(existing["updated_at"]) if existing["updated_at"] else None
    if stored and incoming < stored:
        return _decode(existing)  # stale re-sync: keep stored
    fields = data.model_dump(exclude_unset=True)
    sets, params = [], []
    simple = ["display_name", "contact", "region", "lat", "lon", "availability",
              "mobility", "notes"]
    for col in simple:
        if col in fields:
            sets.append(f"{col} = ?")
            params.append(fields[col])
    if "languages" in fields:
        sets.append("languages = ?")
        params.append(json.dumps(data.languages) if data.languages is not None else None)
    if "skills" in fields:
        sets.append("skills = ?")
        params.append(json.dumps(data.skills) if data.skills is not None else None)
    if "visible" in fields:
        sets.append("visible = ?")
        params.append(1 if data.visible else 0)
    sets.append("updated_at = ?")
    params.append(incoming)
    params.append(pid)
    conn.execute(f"UPDATE volunteer_profiles SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM volunteer_profiles WHERE id = ?", (pid,)).fetchone()
    _audit(actor, "volunteer_update", pid)
    return _decode(row)


def get_me(user_id: Optional[str], device_id: Optional[str]) -> dict:
    """Return the caller's profile by identity, or 404 if none yet."""
    with db.get_db() as conn:
        row = _find_existing(conn, user_id, device_id, None)
    if not row:
        raise HTTPException(status_code=404, detail="No volunteer profile yet")
    return _decode(row)


def update_me(
    data: VolunteerProfileWrite, user_id: Optional[str], device_id: Optional[str],
    actor: str = "anon",
) -> dict:
    """Patch the caller's existing profile (404 if they have none)."""
    now = now_iso()
    with db.get_db() as conn:
        existing = _find_existing(conn, user_id, device_id or data.device_id, data.id)
        if not existing:
            raise HTTPException(status_code=404, detail="No volunteer profile yet")
        return _update_row(conn, existing, data, now, actor)


def nearby(
    lat: Optional[float] = None, lon: Optional[float] = None,
    radius_m: float = 25000, op_id: Optional[str] = None,
    availability: Optional[str] = "available", skill: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """Discoverable volunteers, optionally near a point or an operation's zone.

    Only ``visible=1`` profiles are returned. When ``op_id`` is given and the
    operation has a zone centre, that centre is used as the search origin (so a
    coordinator can ask "who is near my operation?"). Remote/mobile volunteers
    with no coordinates are still listed (after the geolocated ones) since they
    can help from anywhere. Results without coordinates are kept only when no
    origin is supplied or when they are remote/mobile.
    """
    origin_lat, origin_lon = lat, lon
    if op_id and (origin_lat is None or origin_lon is None):
        with db.get_db() as conn:
            op = conn.execute(
                "SELECT zone_lat, zone_lon FROM sar_operations WHERE id = ?", (op_id,)
            ).fetchone()
        if op and op["zone_lat"] is not None and op["zone_lon"] is not None:
            origin_lat, origin_lon = op["zone_lat"], op["zone_lon"]

    sql = "SELECT * FROM volunteer_profiles WHERE visible = 1"
    params: list = []
    if availability:
        sql += " AND availability = ?"
        params.append(availability)
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    geolocated: List[dict] = []
    remote: List[dict] = []
    for row in rows:
        rec = _decode(row)
        if skill and skill.lower() not in [s.lower() for s in rec.get("skills", [])]:
            continue
        if origin_lat is not None and origin_lon is not None and rec.get("lat") is not None and rec.get("lon") is not None:
            dist = haversine_m(origin_lat, origin_lon, rec["lat"], rec["lon"])
            if dist <= radius_m:
                rec["distance_m"] = round(dist)
                geolocated.append(rec)
        elif rec.get("mobility") in ("remote", "mobile") or origin_lat is None:
            remote.append(rec)
    geolocated.sort(key=lambda r: r["distance_m"])
    results = (geolocated + remote)[:limit]
    return {"records": results, "count": len(results)}


def sync_download(since: Optional[str] = None) -> dict:
    """Pull volunteer profiles changed after ``since`` for offline/mesh use."""
    since = since or "1970-01-01T00:00:00Z"
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM volunteer_profiles WHERE updated_at > ? ORDER BY updated_at ASC",
            (since,),
        ).fetchall()
    return {"records": [_decode(r) for r in rows]}
