"""Shelter & refugee information hub logic (plan-20).

Shelters are promoted from a frontend-only demo list into first-class,
server-backed records: capacity, services, contact info, an official update
feed, check-ins, and a verified-operator claim flow. All of it is additive and
loosely coupled to the rest of the schema by id references.

JSON-array columns (``services``/``supply_needs``/``target_populations`` on a
shelter, ``services_changed`` on an update) are stored as TEXT and decoded here
so the HTTP layer and clients always see real lists/objects. Trust mirrors the
moderation model: official (verified staff) > volunteer > crowd.
"""

import hashlib
import json
import secrets
import uuid
from typing import List, Optional

import db
import jsonutil
from models import (
    ShelterCapacityUpdate,
    ShelterCheckinCreate,
    ShelterClaimRequest,
    ShelterRecord,
    ShelterTokenCreate,
    ShelterUpdateCreate,
    now_iso,
)

# JSON array columns on a shelter row, decoded on read / encoded on write.
_JSON_LIST_COLS = ("services", "supply_needs", "target_populations")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _dumps(value) -> Optional[str]:
    return jsonutil.dumps(value)


def _loads_list(raw) -> list:
    return jsonutil.loads_list(raw)


def _row_to_shelter(row) -> dict:
    d = db.row_to_dict(row)
    for col in _JSON_LIST_COLS:
        d[col] = _loads_list(d.get(col))
    d["accepting_new"] = bool(d.get("accepting_new"))
    return d


# ── Shelters ─────────────────────────────────────────────────────────────────


def list_shelters(
    disaster_id: Optional[str] = None,
    *,
    has_space: bool = False,
    accepts_pets: bool = False,
    has_medical: bool = False,
    needs_supplies: bool = False,
) -> dict:
    """List shelters for a disaster, with optional responder/victim filters.

    Service/population filters use a substring match on the JSON-array TEXT,
    which is exact enough for the small, controlled code vocabulary (a code like
    ``pets`` never collides with another code) and avoids a JSON1 dependency.
    """
    sql = "SELECT * FROM shelters WHERE 1=1"
    params: list = []
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    if has_space:
        # "Has space": explicitly accepting AND (unknown or >0 availability).
        sql += (
            " AND accepting_new = 1"
            " AND (capacity_available IS NULL OR capacity_available > 0)"
        )
    if accepts_pets:
        sql += " AND services LIKE ?"
        params.append('%"pets"%')
    if has_medical:
        sql += " AND services LIKE ?"
        params.append('%"medical"%')
    if needs_supplies:
        sql += " AND supply_needs IS NOT NULL AND supply_needs != '[]' AND supply_needs != ''"
    sql += " ORDER BY name COLLATE NOCASE ASC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [_row_to_shelter(r) for r in rows]}


def get_shelter(shelter_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
        return _row_to_shelter(row) if row else None


def upsert_shelter(shelter: ShelterRecord) -> dict:
    """Create or update a shelter. Timestamp-guarded last-write-wins on update
    so a stale offline/mesh copy can't clobber a newer one (same model as /sync).
    """
    now = now_iso()
    sid = shelter.id or _new_id("shelter")
    incoming_updated = shelter.updatedAt or now
    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT updated_at FROM shelters WHERE id = ?", (sid,)
        ).fetchone()
        if existing and existing["updated_at"] and incoming_updated < existing["updated_at"]:
            # Stale write: keep the newer stored row.
            row = conn.execute("SELECT * FROM shelters WHERE id = ?", (sid,)).fetchone()
            return _row_to_shelter(row)
        conn.execute(
            """
            INSERT INTO shelters
            (id, disaster_id, name, kind, address, lat, lon, phone, whatsapp,
             email, hours, capacity_total, capacity_available, beds_available,
             occupancy, accepting_new, services, supply_needs, target_populations,
             notes, source, trust, operator_user_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              disaster_id=excluded.disaster_id, name=excluded.name, kind=excluded.kind,
              address=excluded.address, lat=excluded.lat, lon=excluded.lon,
              phone=excluded.phone, whatsapp=excluded.whatsapp, email=excluded.email,
              hours=excluded.hours, capacity_total=excluded.capacity_total,
              capacity_available=excluded.capacity_available,
              beds_available=excluded.beds_available, occupancy=excluded.occupancy,
              accepting_new=excluded.accepting_new, services=excluded.services,
              supply_needs=excluded.supply_needs,
              target_populations=excluded.target_populations, notes=excluded.notes,
              source=excluded.source, trust=excluded.trust,
              operator_user_id=excluded.operator_user_id, updated_at=excluded.updated_at
            """,
            (
                sid, shelter.disaster_id, shelter.name, shelter.kind, shelter.address,
                shelter.lat, shelter.lon, shelter.phone, shelter.whatsapp, shelter.email,
                shelter.hours, shelter.capacity_total, shelter.capacity_available,
                shelter.beds_available, shelter.occupancy,
                1 if (shelter.accepting_new is None or shelter.accepting_new) else 0,
                _dumps(shelter.services), _dumps(shelter.supply_needs),
                _dumps(shelter.target_populations), shelter.notes, shelter.source or "web",
                shelter.trust or "crowd", shelter.operator_user_id,
                shelter.createdAt or now, incoming_updated,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM shelters WHERE id = ?", (sid,)).fetchone()
        return _row_to_shelter(row)


def update_capacity(shelter_id: str, patch: ShelterCapacityUpdate) -> Optional[dict]:
    """Apply a partial capacity/availability/needs patch. Only provided fields
    change. Returns the updated shelter, or None if it doesn't exist."""
    sets: list = []
    params: list = []
    simple = {
        "capacity_total": patch.capacity_total,
        "capacity_available": patch.capacity_available,
        "beds_available": patch.beds_available,
        "occupancy": patch.occupancy,
    }
    for col, val in simple.items():
        if val is not None:
            sets.append(f"{col} = ?")
            params.append(val)
    if patch.accepting_new is not None:
        sets.append("accepting_new = ?")
        params.append(1 if patch.accepting_new else 0)
    for col, val in (
        ("services", patch.services),
        ("supply_needs", patch.supply_needs),
        ("target_populations", patch.target_populations),
    ):
        if val is not None:
            sets.append(f"{col} = ?")
            params.append(_dumps(val))
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM shelters WHERE id = ?", (shelter_id,)).fetchone():
            return None
        if sets:
            sets.append("updated_at = ?")
            params.append(now_iso())
            params.append(shelter_id)
            conn.execute(f"UPDATE shelters SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
        row = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
        return _row_to_shelter(row)


# ── Updates feed ─────────────────────────────────────────────────────────────


def list_updates(shelter_id: str, *, include_expired: bool = False) -> dict:
    sql = "SELECT * FROM shelter_updates WHERE shelter_id = ?"
    params: list = [shelter_id]
    if not include_expired:
        sql += " AND (expires_at IS NULL OR expires_at > ?)"
        params.append(now_iso())
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = db.row_to_dict(r)
            if d.get("services_changed"):
                try:
                    d["services_changed"] = json.loads(d["services_changed"])
                except (TypeError, ValueError):
                    pass
            out.append(d)
        return {"records": out}


def add_update(
    shelter_id: str,
    payload: ShelterUpdateCreate,
    *,
    author_role: str = "volunteer",
    author_id: Optional[str] = None,
) -> Optional[dict]:
    """Append an entry to a shelter's feed, applying any structured change.

    ``author_role`` is decided by the caller (route) from the auth context — a
    verified operator posts as ``official``, otherwise ``volunteer``. Clients
    cannot fake it. If the update carries an ``occupancy_delta`` we also nudge
    the shelter's stored occupancy so the capacity bar stays current.
    """
    now = now_iso()
    uid = _new_id("supd")
    role = payload.author_role if payload.author_role in {"official", "volunteer", "system"} else author_role
    with db.get_db() as conn:
        shelter = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
        if not shelter:
            return None
        conn.execute(
            """
            INSERT INTO shelter_updates
            (id, shelter_id, disaster_id, author_id, author_name, author_role,
             message, services_changed, occupancy_delta, source, created_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                uid, shelter_id, shelter["disaster_id"], author_id, payload.author_name,
                role, payload.message,
                json.dumps(payload.services_changed) if payload.services_changed else None,
                payload.occupancy_delta, payload.source or "web",
                payload.createdAt or now, payload.expires_at,
            ),
        )
        # Apply structured side-effects and stamp the shelter's last-update marker.
        sets = ["last_update_at = ?", "last_update_source = ?", "updated_at = ?"]
        params: list = [now, role, now]
        if payload.occupancy_delta:
            cur = shelter["occupancy"] or 0
            sets.append("occupancy = ?")
            params.append(max(0, cur + payload.occupancy_delta))
        params.append(shelter_id)
        conn.execute(f"UPDATE shelters SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        row = conn.execute("SELECT * FROM shelter_updates WHERE id = ?", (uid,)).fetchone()
        return db.row_to_dict(row)


# ── Check-ins ────────────────────────────────────────────────────────────────


def add_checkin(shelter_id: str, payload: ShelterCheckinCreate) -> Optional[dict]:
    now = now_iso()
    cid = payload.id or _new_id("chk")
    with db.get_db() as conn:
        shelter = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
        if not shelter:
            return None
        conn.execute(
            """
            INSERT INTO shelter_checkins
            (id, shelter_id, disaster_id, alias, person_id, note, source, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              alias=excluded.alias, person_id=excluded.person_id, note=excluded.note,
              updated_at=excluded.updated_at
            """,
            (
                cid, shelter_id, shelter["disaster_id"], payload.alias, payload.person_id,
                payload.note, payload.source or "web",
                payload.createdAt or now, payload.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM shelter_checkins WHERE id = ?", (cid,)).fetchone()
        return db.row_to_dict(row)


def list_checkins(shelter_id: str) -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM shelter_checkins WHERE shelter_id = ? ORDER BY created_at DESC",
            (shelter_id,),
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def find_checkins_by_alias(alias: str) -> dict:
    """Family search: the most recent shelter check-in(s) for an alias, joined
    with the shelter name so the UI can show "last seen at <shelter>"."""
    q = (alias or "").strip()
    if not q:
        return {"records": []}
    with db.get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, s.name AS shelter_name
            FROM shelter_checkins c
            LEFT JOIN shelters s ON s.id = c.shelter_id
            WHERE c.alias LIKE ? COLLATE NOCASE
            ORDER BY c.created_at DESC
            LIMIT 20
            """,
            (f"%{q}%",),
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


# ── Verified-operator tokens (plan-20 §9) ────────────────────────────────────


def issue_token(shelter_id: str, payload: ShelterTokenCreate, issued_by: str) -> Optional[dict]:
    """Mint a one-time shelter-claim token. The raw token is returned ONCE and
    only its SHA-256 hash is stored. Returns None if the shelter doesn't exist."""
    raw = secrets.token_urlsafe(24)
    now = now_iso()
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM shelters WHERE id = ?", (shelter_id,)).fetchone():
            return None
        conn.execute(
            """
            INSERT INTO shelter_tokens
            (token_hash, shelter_id, label, issued_by, expires_at, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (_hash_token(raw), shelter_id, payload.label, issued_by, payload.expires_at, now),
        )
        conn.commit()
    return {"token": raw, "shelter_id": shelter_id, "label": payload.label, "created_at": now}


def list_tokens(shelter_id: str) -> dict:
    """List issued tokens for a shelter (hashes only — never the raw token)."""
    with db.get_db() as conn:
        rows = conn.execute(
            """
            SELECT token_hash, shelter_id, label, issued_by, claimed_by_user_id,
                   claimed_at, revoked, expires_at, created_at
            FROM shelter_tokens WHERE shelter_id = ? ORDER BY created_at DESC
            """,
            (shelter_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = db.row_to_dict(r)
            d["token_hint"] = (d.pop("token_hash") or "")[:8]
            d["revoked"] = bool(d["revoked"])
            out.append(d)
        return {"records": out}


def revoke_token(token_hash_prefix: str, shelter_id: str) -> bool:
    """Revoke a token by its hash prefix (the hint shown in list_tokens)."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT token_hash FROM shelter_tokens WHERE shelter_id = ? AND token_hash LIKE ?",
            (shelter_id, f"{token_hash_prefix}%"),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE shelter_tokens SET revoked = 1 WHERE token_hash = ?", (row["token_hash"],)
        )
        conn.commit()
        return True


def claim_shelter(req: ShelterClaimRequest, user: dict) -> Optional[dict]:
    """Redeem a claim token: marks the token claimed and sets the shelter's
    verified operator + bumps its trust to ``official``. Returns the shelter, or
    None if the token is invalid/expired/revoked/already-claimed."""
    token_hash = _hash_token((req.token or "").strip())
    now = now_iso()
    with db.get_db() as conn:
        tok = conn.execute(
            "SELECT * FROM shelter_tokens WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not tok or tok["revoked"] or tok["claimed_by_user_id"]:
            return None
        if tok["expires_at"] and tok["expires_at"] < now:
            return None
        conn.execute(
            "UPDATE shelter_tokens SET claimed_by_user_id = ?, claimed_at = ? WHERE token_hash = ?",
            (user["id"], now, token_hash),
        )
        conn.execute(
            "UPDATE shelters SET operator_user_id = ?, trust = 'official', updated_at = ? WHERE id = ?",
            (user["id"], now, tok["shelter_id"]),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM shelters WHERE id = ?", (tok["shelter_id"],)).fetchone()
        return _row_to_shelter(row) if row else None


def is_operator_of(shelter_id: str, user_id: Optional[str]) -> bool:
    if not user_id:
        return False
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM shelters WHERE id = ? AND operator_user_id = ?",
            (shelter_id, user_id),
        ).fetchone()
        return bool(row)


def roster(shelter_id: str) -> List[dict]:
    """The list of people checked in at a shelter, for an operator handover
    export (CSV/PDF). Plain dict rows; the route formats them."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM shelter_checkins WHERE shelter_id = ? ORDER BY created_at ASC",
            (shelter_id,),
        ).fetchall()
        return [db.row_to_dict(r) for r in rows]
