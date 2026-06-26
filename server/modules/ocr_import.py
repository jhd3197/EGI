"""Paper-import (OCR) logic: create a draft, list/get drafts, review/publish.

The OCR engine, the LLM extractor, and the upload directory are *injected* by
the route layer (they are read from the ``main`` module at request time so the
test suite can monkeypatch ``main.ocr_image`` / ``main.extract_with_llm`` /
``main.UPLOAD_DIR``)."""

import json
import uuid
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, UploadFile

import db
from models import PersonRecord, now_iso


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
    ext = Path(file.filename or "image.jpg").suffix
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = upload_dir / safe_name

    try:
        with open(dest, "wb") as f:
            for chunk in file.file:
                f.write(chunk)
    finally:
        file.file.close()

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
    provenance = f"Extracted from uploaded paper image '{file.filename}' via OCR"

    record = {
        "id": record_id,
        "disaster_id": disaster_id,
        "source": "ocr",
        "provenance": provenance,
        "image_path": f"/uploads/{safe_name}",
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
        conn.execute(
            """
            INSERT INTO persons
            (id, disaster_id, name, status, gender, age, location, last_seen_date,
             clothes, notes, contact, reporter_name, reporter_relation, reporter_country,
             reported_by, source, provenance, image_path, ocr_text, extracted_json,
             confidence, reviewed, cedula, given_name, family_name, created_at, updated_at)
            VALUES
            (:id, :disaster_id, :name, :status, :gender, :age, :location, :last_seen_date,
             :clothes, :notes, :contact, :reporter_name, :reporter_relation, :reporter_country,
             :reported_by, :source, :provenance, :image_path, :ocr_text, :extracted_json,
             :confidence, :reviewed, :cedula, :given_name, :family_name, :created_at, :updated_at)
            """,
            record,
        )
        conn.commit()

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


def review_ocr_import(record_id: str, record: PersonRecord) -> dict:
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
    return {"ok": True, "id": record_id}
