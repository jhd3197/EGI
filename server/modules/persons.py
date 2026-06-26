"""Person CRUD + search logic."""

from typing import Optional

from fastapi import HTTPException

import db


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
    sql += (
        " AND reviewed >= 0"
        " AND NOT (source IN ('ocr','ai_draft','pfif_import') AND reviewed = 0)"
    )
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
        return {"records": [db.row_to_dict(r) for r in rows]}


def get_person(person_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return db.row_to_dict(row)
