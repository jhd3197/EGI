import os
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import db
from ocr import ocr_image, extract_with_llm, sanitize_filename

load_dotenv()

app = FastAPI(title="EGI Sync Server")

PORT = int(os.environ.get("PORT", "3000"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", "../frontend/dist")).resolve()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded images
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


class PersonRecord(BaseModel):
    id: Optional[str] = None
    disaster_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    last_seen_date: Optional[str] = None
    clothes: Optional[str] = None
    notes: Optional[str] = None
    contact: Optional[str] = None
    reporter_name: Optional[str] = None
    reporter_relation: Optional[str] = None
    reporter_country: Optional[str] = None
    reported_by: Optional[str] = None
    source: Optional[str] = "web"
    provenance: Optional[str] = None
    image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_json: Optional[str] = None
    confidence: Optional[float] = None
    reviewed: Optional[int] = 0
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class SyncPayload(BaseModel):
    records: List[PersonRecord]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_status(status: Optional[str]) -> bool:
    return status in {"missing", "found", "safe", "deceased", "sighted", "care", None}


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/health")
def health():
    return {"ok": True, "service": "EGI Sync Server (Python)"}


@app.get("/persons")
def search_persons(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    disaster_id: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    sql = "SELECT * FROM persons WHERE 1=1"
    params: list = []
    if q:
        sql += " AND (name LIKE ? OR notes LIKE ? OR ocr_text LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
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


@app.get("/persons/{person_id}")
def get_person(person_id: str):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return db.row_to_dict(row)


@app.post("/sync")
def sync_upload(payload: SyncPayload):
    if not isinstance(payload.records, list):
        raise HTTPException(status_code=400, detail="records must be an array")

    now = now_iso()
    with db.get_db() as conn:
        cur = conn.cursor()
        for r in payload.records:
            if not r.id:
                raise HTTPException(status_code=400, detail="record id is required")
            if not validate_status(r.status):
                raise HTTPException(status_code=400, detail=f"invalid status: {r.status}")
            values = (
                r.id,
                r.disaster_id,
                r.name,
                r.status,
                r.gender,
                r.age,
                r.location,
                r.last_seen_date,
                r.clothes,
                r.notes,
                r.contact,
                r.reporter_name,
                r.reporter_relation,
                r.reporter_country,
                r.reported_by,
                r.source or "web",
                r.provenance,
                r.image_path,
                r.ocr_text,
                r.extracted_json,
                r.confidence,
                r.reviewed if r.reviewed is not None else 0,
                r.createdAt or now,
                r.updatedAt or now,
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO persons
                (id, disaster_id, name, status, gender, age, location, last_seen_date,
                 clothes, notes, contact, reporter_name, reporter_relation, reporter_country,
                 reported_by, source, provenance, image_path, ocr_text, extracted_json,
                 confidence, reviewed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        conn.commit()
    return {"saved": len(payload.records)}


@app.get("/sync")
def sync_download(since: Optional[str] = None):
    since = since or "1970-01-01T00:00:00Z"
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM persons WHERE updated_at > ? ORDER BY updated_at ASC", (since,)
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


@app.post("/import/paper")
def import_paper(
    file: UploadFile = File(...),
    disaster_id: Optional[str] = Form(None),
    run_llm: bool = Form(True),
):
    """Upload a photo of a paper report, OCR it, and create a draft record.

    The record starts with `reviewed=0` and `source='ocr'` so a human can verify it.
    """
    ext = Path(file.filename or "image.jpg").suffix
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / safe_name

    try:
        with open(dest, "wb") as f:
            for chunk in file.file:
                f.write(chunk)
    finally:
        file.file.close()

    try:
        text, confidence = ocr_image(dest)
    except Exception as exc:
        # Keep the upload so the user can still see the image and type manually
        raise HTTPException(status_code=422, detail=f"OCR failed: {exc}")

    extracted = None
    if run_llm:
        extracted = extract_with_llm(text)

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
        "created_at": now,
        "updated_at": now,
    }

    # Apply LLM-extracted fields if available
    if extracted:
        for key in [
            "name", "status", "gender", "age", "location", "last_seen_date",
            "clothes", "notes", "contact", "reporter_name", "reporter_relation",
            "reporter_country", "reported_by",
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
             confidence, reviewed, created_at, updated_at)
            VALUES
            (:id, :disaster_id, :name, :status, :gender, :age, :location, :last_seen_date,
             :clothes, :notes, :contact, :reporter_name, :reporter_relation, :reporter_country,
             :reported_by, :source, :provenance, :image_path, :ocr_text, :extracted_json,
             :confidence, :reviewed, :created_at, :updated_at)
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


@app.get("/import/paper")
def list_ocr_imports(reviewed: Optional[int] = Query(None)):
    sql = "SELECT * FROM persons WHERE source = 'ocr'"
    params: list = []
    if reviewed is not None:
        sql += " AND reviewed = ?"
        params.append(reviewed)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


@app.get("/import/paper/{record_id}")
def get_ocr_import(record_id: str):
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM persons WHERE id = ? AND source = 'ocr'", (record_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return db.row_to_dict(row)


@app.post("/import/paper/{record_id}/review")
def review_ocr_import(record_id: str, record: PersonRecord):
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


# Serve the frontend SPA. API routes above take precedence.
@app.get("/{path:path}")
def serve_frontend(path: str):
    requested = FRONTEND_DIR / path
    if requested.is_file():
        return FileResponse(requested)
    # For SPA routes, fall back to index.html so the .dc runtime takes over.
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")


if __name__ == "__main__":
    import uvicorn

    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
