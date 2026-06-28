"""Report (PFIF "note") logic: timestamp-guarded upsert, list, create."""

import api_response
import db
import ids
from fastapi import HTTPException

from models import (
    ReportRecord, normalize_ts, now_iso, validate_confidence, validate_status,
)
from modules import crud


def upsert_report(cur, rep: ReportRecord, now: str) -> bool:
    """Timestamp-guarded upsert of one report. Returns False if a stale write was
    skipped (incoming updated_at older than the stored row), True otherwise."""
    rep_id = rep.id or ids.new_id("egi-report")
    incoming_updated = normalize_ts(rep.updatedAt or now)
    if crud.is_stale(cur, "reports", rep_id, incoming_updated):
        return False
    cur.execute(
        """
        INSERT OR REPLACE INTO reports
        (id, person_id, author_name, author_relation, status, note, location,
         source, origin_device, confidence, lat, lon, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rep_id,
            rep.person_id,
            rep.author_name,
            rep.author_relation,
            rep.status,
            rep.note,
            rep.location,
            rep.source or "web",
            rep.origin_device,
            rep.confidence,
            rep.lat,
            rep.lon,
            normalize_ts(rep.createdAt or now),
            incoming_updated,
        ),
    )
    return True


def list_person_reports(person_id: str) -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE person_id = ? ORDER BY created_at DESC",
            (person_id,),
        ).fetchall()
        return api_response.records(db.row_to_dict(r) for r in rows)


def create_person_report(person_id: str, report: ReportRecord) -> dict:
    """Create a report (PFIF note) for a person. person_id comes from the path."""
    if not validate_status(report.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {report.status}")
    if not validate_confidence(report.confidence):
        raise HTTPException(status_code=400, detail=f"invalid confidence: {report.confidence}")
    now = now_iso()
    report.person_id = person_id
    report.id = report.id or ids.new_id("egi-report")
    report.createdAt = report.createdAt or now
    report.updatedAt = report.updatedAt or now
    with db.get_db() as conn:
        cur = conn.cursor()
        upsert_report(cur, report, now)
        conn.commit()
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report.id,)).fetchone()
        return db.row_to_dict(row)
