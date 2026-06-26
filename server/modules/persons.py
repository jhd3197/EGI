"""Person CRUD + search logic."""

from typing import Optional

from fastapi import HTTPException

import db
from modules.confidence import derive_status, derived_status_map
from modules.moderation import UNTRUSTED_SOURCES


def search_persons(
    q: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    disaster_id: Optional[str] = None,
    cedula: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 100,
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
    )
    params.extend(UNTRUSTED_SOURCES)
    if q:
        sql += (
            " AND (name LIKE ? OR notes LIKE ? OR ocr_text LIKE ?"
            " OR given_name LIKE ? OR family_name LIKE ? OR cedula LIKE ?)"
        )
        params.extend([f"%{q}%"] * 6)
    if cedula:
        sql += " AND cedula = ?"
        params.append(cedula)
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
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        records = [db.row_to_dict(r) for r in rows]
        # Read-only derived_status from each person's reports (highest-confidence
        # latest report wins); falls back to the stored status. Batched to avoid N+1.
        derived = derived_status_map(conn, [r["id"] for r in records])
        for rec in records:
            rec["derived_status"] = derived.get(rec["id"]) or rec.get("status")
        return {"records": records}


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
        return record
