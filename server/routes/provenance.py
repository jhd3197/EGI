"""Raw-source provenance read API (plan-24.5).

Operator-gated endpoints that let a moderator trace a record back to the raw
file it came from, including the original filename, SHA-256 hash, extraction
method, and other records from the same batch.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import db
from auth import require_operator

router = APIRouter()


@router.get("/provenance/persons/{person_id}")
def get_person_provenance(person_id: str, operator: str = Depends(require_operator)):
    """Return a person plus its import batch and change history."""
    with db.get_db() as conn:
        person = conn.execute(
            "SELECT * FROM persons WHERE id = ?", (person_id,)
        ).fetchone()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        person_dict = db.row_to_dict(person)
        batch = None
        if person_dict.get("import_batch_id"):
            batch_row = conn.execute(
                "SELECT * FROM import_batches WHERE id = ?",
                (person_dict["import_batch_id"],),
            ).fetchone()
            if batch_row:
                batch = db.row_to_dict(batch_row)

        history = [
            db.row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM record_history WHERE person_id = ? ORDER BY created_at ASC",
                (person_id,),
            ).fetchall()
        ]

    return {
        "person": person_dict,
        "batch": batch,
        "history": history,
    }


@router.get("/provenance/batches/{batch_id}")
def get_batch(batch_id: str, operator: str = Depends(require_operator)):
    """Return a batch plus all persons and reports linked to it."""
    with db.get_db() as conn:
        batch_row = conn.execute(
            "SELECT * FROM import_batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if not batch_row:
            raise HTTPException(status_code=404, detail="Batch not found")

        persons = [
            db.row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM persons WHERE import_batch_id = ? ORDER BY created_at ASC",
                (batch_id,),
            ).fetchall()
        ]
        reports = [
            db.row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM reports WHERE import_batch_id = ? ORDER BY created_at ASC",
                (batch_id,),
            ).fetchall()
        ]

    return {
        "batch": db.row_to_dict(batch_row),
        "persons": persons,
        "reports": reports,
        "counts": {"persons": len(persons), "reports": len(reports)},
    }


@router.get("/provenance/batches")
def list_batches(
    disaster_id: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    operator: str = Depends(require_operator),
):
    """List import batches with optional filters."""
    sql = "SELECT * FROM import_batches WHERE 1=1"
    params: list = []
    if disaster_id:
        sql += " AND disaster_id = ?"
        params.append(disaster_id)
    if source_type:
        sql += " AND source_type = ?"
        params.append(source_type)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM import_batches WHERE 1=1"
            + (" AND disaster_id = ?" if disaster_id else "")
            + (" AND source_type = ?" if source_type else "")
            + (" AND status = ?" if status else ""),
            [p for p in [disaster_id, source_type, status] if p is not None],
        ).fetchone()[0]

    return {
        "batches": [db.row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
