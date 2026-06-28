"""Missing/found animal (pet) registry logic (plan-28).

Animals are a PARALLEL track to person records — a separate table, UI and search,
NEVER mixed with the missing-person registry (a pet must never become a person
record). They ride the SAME mesh envelope + cloud ``/sync`` path as persons with
timestamp-guarded last-write-wins on ``id``, always tagged ``record_type='animal'``.

Trust mirrors persons: the ``reviewed`` flag is the gate (0 pending, 1 approved,
-1 soft-deleted) and ``UNTRUSTED_SOURCES`` rows stay hidden from public search
until a moderator approves them, while normal crowd ``source='web'`` reports stay
visible at ``reviewed=0`` — exactly like ordinary person web reports. The
``photos`` JSON-array column is decoded here so the HTTP layer always sees a list.
"""

import json
import uuid
from typing import List, Optional

from fastapi import HTTPException

import db
from models import AnimalRecord, now_iso, normalize_ts, validate_animal_status
from modules import audit
from modules.moderation import UNTRUSTED_SOURCES

# Columns persisted on an animals row, in INSERT order (also the upsert column
# list). `created_at`/`updated_at` are appended explicitly by the writer.
_COLUMNS = (
    "id", "record_type", "disaster_id", "status", "species", "breed", "name",
    "sex", "size", "color", "distinguishing_marks", "microchip", "photo_url",
    "photos", "last_seen_location", "last_seen_at", "lat", "lon", "owner_name",
    "owner_contact", "reporter_id", "reporter_name", "notes", "source",
    "reviewed", "origin_device", "hop_count", "merged_into", "shelter_id",
    "intake_at", "condition_note",
)


def _new_id() -> str:
    return f"animal-{uuid.uuid4().hex[:12]}"


def _dumps(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(list(value))
    except (TypeError, ValueError):
        return None


def _loads_list(raw) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _row_to_animal(row) -> dict:
    d = db.row_to_dict(row)
    d["photos"] = _loads_list(d.get("photos"))
    return d


def _protect_contact(d: dict) -> dict:
    """Strip the owner's contact from a record before it leaves in a list/detail
    response (plan-28 Phase 6). Bulk scraping a registry of phone numbers is an
    abuse vector, so the contact is revealed only via the rate-limited
    ``reveal_contact`` endpoint. A ``has_owner_contact`` boolean tells the UI
    whether a reveal button is worth showing."""
    d = dict(d)
    d["has_owner_contact"] = bool(d.get("owner_contact"))
    d.pop("owner_contact", None)
    return d


# ── Reads ────────────────────────────────────────────────────────────────────


def list_animals(
    disaster_id: Optional[str] = None,
    *,
    species: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    shelter_id: Optional[str] = None,
    include_unreviewed: bool = False,
    limit: int = 200,
) -> dict:
    """Public animal search with the same trust gate as persons.

    Hides soft-deleted (``reviewed=-1``) and merged (``merged_into IS NOT NULL``)
    rows, and untrusted-source rows still pending review — but keeps normal crowd
    ``source='web'`` reports visible at ``reviewed=0``. Pass
    ``include_unreviewed`` (operator/moderation view) to see the pending queue.
    """
    sql = "SELECT * FROM animals WHERE merged_into IS NULL"
    params: list = []
    if not include_unreviewed:
        placeholders = ",".join("?" for _ in UNTRUSTED_SOURCES)
        sql += (
            " AND reviewed != -1"
            f" AND NOT (reviewed = 0 AND source IN ({placeholders}))"
        )
        params.extend(UNTRUSTED_SOURCES)
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    if species:
        sql += " AND species = ?"
        params.append(species)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if location:
        sql += " AND last_seen_location LIKE ? COLLATE NOCASE"
        params.append(f"%{location}%")
    if shelter_id:
        sql += " AND shelter_id = ?"
        params.append(shelter_id)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, min(limit, 1000)))
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [_protect_contact(_row_to_animal(r)) for r in rows]}


def get_animal(animal_id: str) -> Optional[dict]:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM animals WHERE id = ?", (animal_id,)).fetchone()
        return _protect_contact(_row_to_animal(row)) if row else None


def reveal_contact(animal_id: str) -> Optional[dict]:
    """Return the owner's contact for one animal (the rate-limited reveal path,
    plan-28 Phase 6). Returns None if the animal doesn't exist."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT owner_name, owner_contact FROM animals WHERE id = ?", (animal_id,)
        ).fetchone()
        if not row:
            return None
        return {"owner_name": row["owner_name"], "owner_contact": row["owner_contact"]}


def set_reviewed(animal_id: str, value: int, *, actor: str = "op:anonymous") -> dict:
    """Set an animal's moderation trust flag (1 approved, -1 rejected/soft-delete,
    0 pending). Used when a moderator resolves a flag against an animal record."""
    now = now_iso()
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE animals SET reviewed = ?, updated_at = ? WHERE id = ?",
            (value, now, animal_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Animal not found")
        conn.commit()
    audit.log_action(actor, "animal_review", "animal", animal_id, detail=f"reviewed={value}")
    return {"ok": True, "id": animal_id, "reviewed": value}


# ── Writes ───────────────────────────────────────────────────────────────────


def upsert_animal(animal: AnimalRecord) -> dict:
    """Create or update an animal record with timestamp-guarded last-write-wins
    on ``id`` (same model as /sync), so a stale offline/mesh copy can't clobber a
    newer one. Preserves a server-side merge decision across re-syncs."""
    if not validate_animal_status(animal.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {animal.status}")
    now = now_iso()
    aid = animal.id or _new_id()
    incoming_updated = normalize_ts(animal.updatedAt or now)
    created_at = normalize_ts(animal.createdAt or now)
    with db.get_db() as conn:
        existing = conn.execute(
            "SELECT updated_at, merged_into FROM animals WHERE id = ?", (aid,)
        ).fetchone()
        if existing and existing["updated_at"] and incoming_updated < normalize_ts(existing["updated_at"]):
            row = conn.execute("SELECT * FROM animals WHERE id = ?", (aid,)).fetchone()
            return _row_to_animal(row)
        # Incoming wins only if it explicitly set a merge target; otherwise keep
        # any server-side merge decision (INSERT OR REPLACE rewrites the whole row).
        merged_into = animal.merged_into or (existing["merged_into"] if existing else None)
        values = (
            aid,
            "animal",
            animal.disaster_id,
            animal.status,
            animal.species,
            animal.breed,
            animal.name,
            animal.sex,
            animal.size,
            animal.color,
            animal.distinguishing_marks,
            animal.microchip,
            animal.photo_url,
            _dumps(animal.photos),
            animal.last_seen_location,
            animal.last_seen_at,
            animal.lat,
            animal.lon,
            animal.owner_name,
            animal.owner_contact,
            animal.reporter_id,
            animal.reporter_name,
            animal.notes,
            animal.source or "web",
            animal.reviewed if animal.reviewed is not None else 0,
            animal.origin_device,
            animal.hop_count if animal.hop_count is not None else 0,
            merged_into,
            animal.shelter_id,
            animal.intake_at,
            animal.condition_note,
            created_at,
            incoming_updated,
        )
        placeholders = ",".join("?" for _ in range(len(_COLUMNS) + 2))
        conn.execute(
            f"INSERT OR REPLACE INTO animals ({', '.join(_COLUMNS)}, created_at, updated_at) "
            f"VALUES ({placeholders})",
            values,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM animals WHERE id = ?", (aid,)).fetchone()
        return _row_to_animal(row)


def set_status(animal_id: str, status: str, *, actor: str = "op:anonymous") -> dict:
    """Change an animal's status (missing→seen→found→reunited…). Bumps updated_at
    so the change wins LWW and propagates over the mesh."""
    if not validate_animal_status(status) or status is None:
        raise HTTPException(status_code=400, detail=f"invalid status: {status}")
    now = now_iso()
    with db.get_db() as conn:
        cur = conn.execute(
            "UPDATE animals SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, animal_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Animal not found")
        conn.commit()
        row = conn.execute("SELECT * FROM animals WHERE id = ?", (animal_id,)).fetchone()
    audit.log_action(actor, "animal_status", "animal", animal_id, detail=f"status={status}")
    return _row_to_animal(row)


# ── Sync helpers (used by modules/sync.py) ───────────────────────────────────


def sync_upsert(cur, animal: AnimalRecord, now: str) -> bool:
    """Upsert one animal inside an open /sync transaction. Returns False when the
    incoming record is stale (older than the stored row) so the caller can count
    it as skipped. Mirrors persons' timestamp-guarded last-write-wins."""
    if not animal.id:
        raise HTTPException(status_code=400, detail="animal id is required")
    if not validate_animal_status(animal.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {animal.status}")
    incoming_updated = normalize_ts(animal.updatedAt or now)
    created_at = normalize_ts(animal.createdAt or now)
    existing = cur.execute(
        "SELECT updated_at, merged_into FROM animals WHERE id = ?", (animal.id,)
    ).fetchone()
    if existing and existing["updated_at"] and incoming_updated < normalize_ts(existing["updated_at"]):
        return False
    merged_into = animal.merged_into or (existing["merged_into"] if existing else None)
    values = (
        animal.id, "animal", animal.disaster_id, animal.status, animal.species,
        animal.breed, animal.name, animal.sex, animal.size, animal.color,
        animal.distinguishing_marks, animal.microchip, animal.photo_url,
        _dumps(animal.photos), animal.last_seen_location, animal.last_seen_at,
        animal.lat, animal.lon, animal.owner_name, animal.owner_contact,
        animal.reporter_id, animal.reporter_name, animal.notes,
        animal.source or "web", animal.reviewed if animal.reviewed is not None else 0,
        animal.origin_device, animal.hop_count if animal.hop_count is not None else 0,
        merged_into, animal.shelter_id, animal.intake_at, animal.condition_note,
        created_at, incoming_updated,
    )
    placeholders = ",".join("?" for _ in range(len(_COLUMNS) + 2))
    cur.execute(
        f"INSERT OR REPLACE INTO animals ({', '.join(_COLUMNS)}, created_at, updated_at) "
        f"VALUES ({placeholders})",
        values,
    )
    return True


# ── Shelter-held animals (plan-28 Phase 4) ───────────────────────────────────


def list_shelter_animals(shelter_id: str) -> dict:
    """Animals a shelter/clinic is holding. Public — an owner searching for their
    pet needs this without an account. Hides soft-deleted/merged rows but shows
    all trust tiers (a shelter intake is itself a trust signal)."""
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM animals WHERE shelter_id = ? AND merged_into IS NULL "
            "AND reviewed != -1 ORDER BY COALESCE(intake_at, updated_at) DESC",
            (shelter_id,),
        ).fetchall()
        return {"records": [_protect_contact(_row_to_animal(r)) for r in rows]}


def add_shelter_animal(shelter_id: str, animal: AnimalRecord, *, actor: str = "op:anonymous") -> dict:
    """A shelter operator records an animal it is holding. The animal is tagged
    with the shelter, marked ``source='shelter'`` and trusted (``reviewed=1``,
    since an authorized shelter writer is posting it), and defaults to status
    ``found`` (in care) and an intake timestamp of now when unset."""
    now = now_iso()
    animal.shelter_id = shelter_id
    animal.source = "shelter"
    animal.reviewed = 1
    if not animal.status:
        animal.status = "found"
    if not animal.intake_at:
        animal.intake_at = now
    result = upsert_animal(animal)
    audit.log_action(actor, "shelter_animal_add", "animal", result["id"], detail=f"shelter={shelter_id}")
    return result


def changed_since(since: Optional[str] = None) -> List[dict]:
    """Animal records updated after ``since`` (for the /sync download half)."""
    since = since or "1970-01-01T00:00:00Z"
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM animals WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        return [_row_to_animal(r) for r in rows]
