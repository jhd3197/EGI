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
