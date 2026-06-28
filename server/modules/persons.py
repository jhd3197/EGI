"""Person CRUD + search logic."""

import base64
import re
from typing import Optional

from fastapi import HTTPException

import db
from modules.confidence import derive_status, derived_status_map
from modules.moderation import UNTRUSTED_SOURCES
from security import photos_enabled

# Photo fields blanked from public responses when ENABLE_PHOTOS is off, so a URL
# to a crisis photo is never even disclosed (defense in depth alongside the
# operator-gated /uploads route).
_PHOTO_FIELDS = ("image_path", "photo_url")


def _redact_photos(record: dict) -> dict:
    if not photos_enabled():
        for field in _PHOTO_FIELDS:
            if field in record:
                record[field] = None
    # Raw-source provenance (plan-24.5) is operator-only: the batch id links to
    # the original filename/hash/uploader behind the /provenance/* operator gate,
    # so it must never leak through the public person reads (search, get, nearby).
    record.pop("import_batch_id", None)
    return record

# SQL expression that soft-normalizes a stored cedula for comparison: uppercase,
# then strip dots, spaces and dashes. A leading V/E prefix is handled by also
# comparing against 'V'||digits / 'E'||digits below (see _cedula_clause).
_CEDULA_NORM_SQL = (
    "REPLACE(REPLACE(REPLACE(UPPER(COALESCE(cedula,'')),'.',''),' ',''),'-','')"
)


def normalize_cedula(value: str) -> str:
    """Strip dots/spaces/dashes and an optional V-/E- prefix; return the digits.

    `V-26.345.789`, `26.345.789`, `26345789` all normalize to `26345789`.
    """
    s = re.sub(r"[.\s-]", "", (value or "").upper())
    s = re.sub(r"^[VE]", "", s)
    return s


def _cedula_clause(cedula: str) -> tuple[str, list]:
    """Build a WHERE fragment matching exact OR soft-normalized cedula."""
    norm = normalize_cedula(cedula)
    clause = (
        " AND (cedula = ?"
        f" OR {_CEDULA_NORM_SQL} = ?"
        f" OR {_CEDULA_NORM_SQL} = 'V' || ?"
        f" OR {_CEDULA_NORM_SQL} = 'E' || ?)"
    )
    return clause, [cedula, norm, norm, norm]


def _encode_cursor(updated_at: str, rec_id: str) -> str:
    raw = f"{updated_at or ''}|{rec_id or ''}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> Optional[tuple[str, str]]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        updated_at, rec_id = raw.split("|", 1)
        return updated_at, rec_id
    except Exception:
        return None


def search_persons(
    q: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    disaster_id: Optional[str] = None,
    cedula: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 100,
    cursor: Optional[str] = None,
) -> dict:
    sql = "SELECT * FROM persons WHERE 1=1"
    params: list = []
    # Public-search trust gate (moderation): never surface rejected rows
    # (reviewed=-1), and hide untrusted-source records (OCR/AI/PFIF) until a
    # moderator approves them (reviewed=1). Trusted web/seed records with
    # reviewed=0 stay visible.
    untrusted = ",".join("?" * len(UNTRUSTED_SOURCES))
    sql += (
        " AND reviewed >= 0"
        f" AND NOT (source IN ({untrusted}) AND reviewed = 0)"
        # Hide soft-deleted duplicates merged into a canonical record.
        " AND merged_into IS NULL"
        # Abuse prevention (plan-25 Phase 5): hide records whose origin device has
        # been banned, so a blocklisted device's earlier data also disappears.
        " AND (origin_device IS NULL OR origin_device NOT IN"
        " (SELECT device_id FROM device_reputation WHERE banned = 1))"
    )
    params.extend(UNTRUSTED_SOURCES)
    if q:
        sql += (
            " AND (name LIKE ? OR notes LIKE ? OR ocr_text LIKE ?"
            " OR given_name LIKE ? OR family_name LIKE ? OR cedula LIKE ?)"
        )
        params.extend([f"%{q}%"] * 6)
    if cedula:
        # Exact + soft-normalized cedula match (strips dots/spaces/V-E prefix).
        clause, cedula_params = _cedula_clause(cedula)
        sql += clause
        params.extend(cedula_params)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    if since:
        sql += " AND updated_at > ?"
        params.append(since)
    # Cursor-based pagination: stable ordering by (updated_at DESC, id DESC).
    # The cursor encodes the last row of the previous page; keyset-seek past it.
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            c_updated, c_id = decoded
            sql += " AND (updated_at < ? OR (updated_at = ? AND id < ?))"
            params.extend([c_updated, c_updated, c_id])
    sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
    # Fetch one extra row to know whether another page exists.
    params.append(limit + 1)

    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        records = [db.row_to_dict(r) for r in rows]
        has_more = len(records) > limit
        if has_more:
            records = records[:limit]
        next_cursor = (
            _encode_cursor(records[-1].get("updated_at"), records[-1].get("id"))
            if has_more and records
            else None
        )
        # Read-only derived_status from each person's reports (highest-confidence
        # latest report wins); falls back to the stored status. Batched to avoid N+1.
        derived = derived_status_map(conn, [r["id"] for r in records])
        for rec in records:
            rec["derived_status"] = derived.get(rec["id"]) or rec.get("status")
            _redact_photos(rec)
        return {"records": records, "next_cursor": next_cursor, "has_more": has_more}


def get_person(person_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        record = db.row_to_dict(row)
        reports = conn.execute(
            "SELECT id, status, confidence, updated_at FROM reports WHERE person_id = ?",
            (person_id,),
        ).fetchall()
        record["derived_status"] = derive_status(
            [db.row_to_dict(r) for r in reports], record.get("status")
        )
        return _redact_photos(record)
