"""Raw-source provenance helpers (plan-24.5).

Shared utilities for computing file hashes and creating import_batches rows.
Used by CSV/Excel imports, OCR imports, and (optionally) PFIF imports.
"""

import hashlib
import json
import uuid
from typing import Optional

import db
from models import now_iso


def hash_bytes(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def create_import_batch(
    conn,
    *,
    file_bytes: bytes,
    source_type: str,
    extraction_method: str,
    original_filename: Optional[str] = None,
    stored_filename: Optional[str] = None,
    media_type: Optional[str] = None,
    disaster_id: Optional[str] = None,
    uploaded_by: str = "system",
) -> str:
    """Create an import_batches row and return its id.

    The caller is responsible for committing and for updating record_count/status
    after processing.
    """
    batch_id = f"egi-batch-{uuid.uuid4().hex[:12]}"
    now = now_iso()
    conn.execute(
        """
        INSERT INTO import_batches
        (id, disaster_id, source_type, original_filename, stored_filename,
         file_hash, file_size, media_type, extraction_method, status,
         uploaded_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            disaster_id,
            source_type,
            original_filename,
            stored_filename,
            hash_bytes(file_bytes),
            len(file_bytes),
            media_type,
            extraction_method,
            "pending",
            uploaded_by,
            now,
            now,
        ),
    )
    return batch_id


def finalize_batch(
    conn,
    batch_id: str,
    record_count: int,
    errors: Optional[list] = None,
) -> None:
    """Stamp record_count, status and errors on an import_batches row."""
    now = now_iso()
    status = "processed"
    if errors:
        status = "partial" if record_count > 0 else "failed"
    conn.execute(
        """
        UPDATE import_batches
        SET record_count = ?, status = ?, error_log = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            record_count,
            status,
            json.dumps(errors) if errors else None,
            now,
            batch_id,
        ),
    )


def get_person_provenance(person_id: str) -> Optional[dict]:
    """Return a person plus its import batch and change history.

    Returns None if the person does not exist.
    """
    with db.get_db() as conn:
        person = conn.execute(
            "SELECT * FROM persons WHERE id = ?", (person_id,)
        ).fetchone()
        if not person:
            return None

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


def get_batch_provenance(batch_id: str) -> Optional[dict]:
    """Return a batch plus all persons and reports linked to it.

    Returns None if the batch does not exist.
    """
    with db.get_db() as conn:
        batch_row = conn.execute(
            "SELECT * FROM import_batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if not batch_row:
            return None

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


def list_batches(
    *,
    disaster_id: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """List import batches with optional filters, ordered newest-first."""
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
