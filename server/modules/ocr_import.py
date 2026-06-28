"""Paper-import (OCR) logic: create a draft, list/get drafts, review/publish.

The OCR engine, the LLM extractor, and the upload directory are *injected* by
the route layer (they are read from the ``main`` module at request time so the
test suite can monkeypatch ``main.ocr_image`` / ``main.extract_with_llm`` /
``main.UPLOAD_DIR``)."""

import json
import logging
import uuid
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, UploadFile

import db
import uploads
from models import PersonRecord, now_iso
from modules import audit, provenance

logger = logging.getLogger("egi.ocr_import")

# Upload guardrails (plan-07 §12.1) live in the shared uploads module now;
# re-exported here for backward compatibility with existing importers.
from uploads import ALLOWED_IMAGE_EXTS, MAX_UPLOAD_BYTES


def create_paper_import(
    file: UploadFile,
    disaster_id: Optional[str],
    run_llm: bool,
    upload_dir: Path,
    ocr_fn: Callable,
    extract_fn: Callable,
) -> dict:
    """Upload a photo of a paper report, OCR it, and create a draft record.

    The record starts with `reviewed=0` and `source='ocr'` so a human can verify it.
    """
    # Reject non-image uploads up front so /import/paper can't be used as a file
    # drop, then stream to disk under the size cap (shared uploads helpers).
    ext = uploads.validate_image_upload(file)

    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = upload_dir / safe_name

    uploads.save_upload(file, dest, MAX_UPLOAD_BYTES)

    # Strip EXIF (GPS/camera/timestamps) before the image is stored or served.
    # Best-effort: non-image uploads are left untouched. Done before OCR so the
    # on-disk copy never carries metadata, even transiently.
    from ocr import strip_exif

    strip_exif(dest)

    # Hash the stored image for provenance before OCR runs.
    image_bytes = dest.read_bytes()

    try:
        text, confidence = ocr_fn(dest)
    except Exception as exc:
        # Keep the upload so the user can still see the image and type manually
        raise HTTPException(status_code=422, detail=f"OCR failed: {exc}")

    extracted = None
    if run_llm:
        extracted = extract_fn(text)

    record_id = f"egi-ocr-{uuid.uuid4().hex[:8]}"
    now = now_iso()
    provenance_str = f"Extracted from uploaded paper image '{file.filename}' via OCR"

    record = {
        "id": record_id,
        "disaster_id": disaster_id,
        "source": "ocr",
        "provenance": provenance_str,
        "image_path": uploads.url(safe_name),
        "ocr_text": text,
        "extracted_json": json.dumps(extracted) if extracted else None,
        "confidence": confidence,
        "reviewed": 0,
        # Every column referenced by the INSERT must have a value: the named
        # bindings below resolve from this dict, so default the person fields to
        # None up front. They are overwritten by extracted values when the LLM
        # returns them (and stay None when extraction is skipped or partial).
        "name": None,
        "status": None,
        "gender": None,
        "age": None,
        "location": None,
        "last_seen_date": None,
        "clothes": None,
        "notes": None,
        "contact": None,
        "reporter_name": None,
        "reporter_relation": None,
        "reporter_country": None,
        "reported_by": None,
        "cedula": None,
        "given_name": None,
        "family_name": None,
        "created_at": now,
        "updated_at": now,
    }

    # Apply LLM-extracted fields if available
    if extracted:
        for key in [
            "name", "status", "gender", "age", "location", "last_seen_date",
            "clothes", "notes", "contact", "reporter_name", "reporter_relation",
            "reporter_country", "reported_by", "cedula", "given_name", "family_name",
        ]:
            if extracted.get(key):
                record[key] = extracted[key]

    with db.get_db() as conn:
        # Create a provenance batch for the uploaded image.
        extraction_method = "tesseract+llm" if run_llm else "tesseract"
        batch_id = provenance.create_import_batch(
            conn,
            file_bytes=image_bytes,
            source_type="ocr",
            extraction_method=extraction_method,
            original_filename=file.filename,
            stored_filename=safe_name,
            media_type=file.content_type or f"image/{ext.lstrip('.').lower()}",
            disaster_id=disaster_id,
            uploaded_by="ocr-import",
        )
        record["import_batch_id"] = batch_id

        conn.execute(
            """
            INSERT INTO persons
            (id, disaster_id, name, status, gender, age, location, last_seen_date,
             clothes, notes, contact, reporter_name, reporter_relation, reporter_country,
             reported_by, source, provenance, image_path, ocr_text, extracted_json,
             confidence, reviewed, cedula, given_name, family_name, import_batch_id,
             created_at, updated_at)
            VALUES
            (:id, :disaster_id, :name, :status, :gender, :age, :location, :last_seen_date,
             :clothes, :notes, :contact, :reporter_name, :reporter_relation, :reporter_country,
             :reported_by, :source, :provenance, :image_path, :ocr_text, :extracted_json,
             :confidence, :reviewed, :cedula, :given_name, :family_name, :import_batch_id,
             :created_at, :updated_at)
            """,
            record,
        )
        provenance.finalize_batch(conn, batch_id, record_count=1)
        conn.commit()

    audit.log_history(record_id, "create", actor="ocr-import", source="ocr")

    # Match the fresh OCR draft against the registry (plan-27 Phase 5) so probable
    # duplicates are queued for review before a moderator publishes it. Best-effort:
    # a dedup failure must never break the import. Lazy import avoids a cycle.
    try:
        from modules import dedup

        dedup.generate_candidates_for(record_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[EGI ocr] candidate scan skipped for {record_id}: {exc}")

    return {
        "id": record_id,
        "image_path": record["image_path"],
        "ocr_text": text,
        "extracted": extracted,
        "confidence": confidence,
        "reviewed": False,
        "message": "Draft record created. Review before publishing.",
    }


def list_ocr_imports(reviewed: Optional[int] = None) -> dict:
    sql = "SELECT * FROM persons WHERE source = 'ocr'"
    params: list = []
    if reviewed is not None:
        sql += " AND reviewed = ?"
        params.append(reviewed)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


def get_ocr_import(record_id: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM persons WHERE id = ? AND source = 'ocr'", (record_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return db.row_to_dict(row)


def review_ocr_import(
    record_id: str, record: PersonRecord, operator: str = "op:anonymous"
) -> dict:
    """Approve or edit an OCR draft record. Set reviewed=1 to publish."""
    now = now_iso()
    data = record.model_dump(exclude_unset=True)
    data.pop("id", None)
    data["updated_at"] = now
    data["reviewed"] = data.get("reviewed", 1)

    fields = ", ".join(f"{k} = ?" for k in data.keys())
    values = list(data.values()) + [record_id]

    with db.get_db() as conn:
        cur = conn.execute(f"UPDATE persons SET {fields} WHERE id = ?", values)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
    audit.log_action(
        operator, "review_ocr", "person", record_id,
        detail=f"reviewed={data['reviewed']}",
    )
    audit.log_history(record_id, "review", actor=operator, source="ocr")
    return {"ok": True, "id": record_id}
