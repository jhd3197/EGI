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
    # PFIF-aligned fields. snake_case in BOTH JSON and DB (no camel mapping).
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    cedula: Optional[str] = None
    sex: Optional[str] = None
    photo_url: Optional[str] = None
    last_known_location: Optional[str] = None
    # Mesh provenance. snake_case in BOTH JSON and DB (no camel mapping).
    origin_device: Optional[str] = None
    hop_count: Optional[int] = 0
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class ReportRecord(BaseModel):
    """A report/observation attached to a person (PFIF "note" concept)."""

    id: Optional[str] = None
    person_id: Optional[str] = None
    author_name: Optional[str] = None
    author_relation: Optional[str] = None
    status: Optional[str] = None
    note: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = "web"
    origin_device: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class SyncPayload(BaseModel):
    records: List[PersonRecord]
    reports: Optional[List[ReportRecord]] = None


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
    cedula: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    sql = "SELECT * FROM persons WHERE 1=1"
    params: list = []
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
    skipped = 0
    with db.get_db() as conn:
        cur = conn.cursor()
        for r in payload.records:
            if not r.id:
                raise HTTPException(status_code=400, detail="record id is required")
            if not validate_status(r.status):
                raise HTTPException(status_code=400, detail=f"invalid status: {r.status}")
            # Timestamp-guarded last-write-wins: the same record reaches the cloud
            # via many mesh paths and often OUT OF ORDER, so a stale relay must not
            # clobber a newer update. Compare updated_at (ISO-8601 UTC sorts
            # lexicographically; clients normalize to a 'Z' suffix). Ties replace so
            # equal-timestamp corrections still apply.
            incoming_updated = r.updatedAt or now
            existing = cur.execute(
                "SELECT updated_at FROM persons WHERE id = ?", (r.id,)
            ).fetchone()
            if existing and existing[0] and incoming_updated < existing[0]:
                skipped += 1
                continue
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
                r.given_name,
                r.family_name,
                r.cedula,
                r.sex,
                r.photo_url,
                r.last_known_location,
                r.origin_device,
                r.hop_count if r.hop_count is not None else 0,
                r.createdAt or now,
                r.updatedAt or now,
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO persons
                (id, disaster_id, name, status, gender, age, location, last_seen_date,
                 clothes, notes, contact, reporter_name, reporter_relation, reporter_country,
                 reported_by, source, provenance, image_path, ocr_text, extracted_json,
                 confidence, reviewed, given_name, family_name, cedula, sex, photo_url,
                 last_known_location, origin_device, hop_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

        reports = payload.reports or []
        reports_skipped = 0
        for rep in reports:
            if not _upsert_report(cur, rep, now):
                reports_skipped += 1

        conn.commit()

    saved = len(payload.records) - skipped
    saved_reports = len(reports) - reports_skipped
    _log_sync(direction="in", record_count=saved,
              detail=f"persons={saved}/{len(payload.records)} "
                     f"reports={saved_reports}/{len(reports)} (stale skipped: "
                     f"{skipped}+{reports_skipped})")
    return {
        "saved": saved,
        "reports": saved_reports,
        "skipped": skipped + reports_skipped,
    }


def _upsert_report(cur, rep: ReportRecord, now: str) -> bool:
    """Timestamp-guarded upsert of one report. Returns False if a stale write was
    skipped (incoming updated_at older than the stored row), True otherwise."""
    rep_id = rep.id or f"egi-report-{uuid.uuid4().hex[:8]}"
    incoming_updated = rep.updatedAt or now
    existing = cur.execute(
        "SELECT updated_at FROM reports WHERE id = ?", (rep_id,)
    ).fetchone()
    if existing and existing[0] and incoming_updated < existing[0]:
        return False
    cur.execute(
        """
        INSERT OR REPLACE INTO reports
        (id, person_id, author_name, author_relation, status, note, location,
         source, origin_device, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            rep.createdAt or now,
            incoming_updated,
        ),
    )
    return True


def _log_sync(direction: str, record_count: int, detail: str = "",
              peer: Optional[str] = None, origin_device: Optional[str] = None) -> None:
    """Best-effort sync audit row. Never raises so it can't break a sync."""
    try:
        with db.get_db() as conn:
            conn.execute(
                """
                INSERT INTO sync_log
                (direction, peer, origin_device, record_count, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (direction, peer, origin_device, record_count, detail, now_iso()),
            )
            conn.commit()
    except Exception:
        pass


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


# ---------------------------------------------------------------------------
# Events, cities, incidents, reports (PFIF-aligned domain objects)
# ---------------------------------------------------------------------------

class EventRecord(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    region: Optional[str] = None
    type: Optional[str] = None
    tag: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class CityRecord(BaseModel):
    id: Optional[str] = None
    event_id: Optional[str] = None
    name: Optional[str] = None
    region: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class IncidentRecord(BaseModel):
    id: Optional[str] = None
    event_id: Optional[str] = None
    kind: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


@app.get("/events")
def list_events():
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC"
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


@app.post("/events")
def upsert_event(event: EventRecord):
    now = now_iso()
    event_id = event.id or f"egi-event-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO events
            (id, name, region, type, tag, date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, event.name, event.region, event.type, event.tag,
                event.date, event.status, event.createdAt or now,
                event.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return db.row_to_dict(row)


@app.get("/cities")
def list_cities(event_id: Optional[str] = Query(None)):
    sql = "SELECT * FROM cities WHERE 1=1"
    params: list = []
    if event_id:
        sql += " AND event_id = ?"
        params.append(event_id)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


@app.post("/cities")
def upsert_city(city: CityRecord):
    now = now_iso()
    city_id = city.id or f"egi-city-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO cities
            (id, event_id, name, region, lat, lon, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                city_id, city.event_id, city.name, city.region, city.lat,
                city.lon, city.createdAt or now, city.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cities WHERE id = ?", (city_id,)).fetchone()
        return db.row_to_dict(row)


@app.get("/incidents")
def list_incidents(event_id: Optional[str] = Query(None)):
    sql = "SELECT * FROM incidents WHERE 1=1"
    params: list = []
    if event_id:
        sql += " AND event_id = ?"
        params.append(event_id)
    sql += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


@app.post("/incidents")
def upsert_incident(incident: IncidentRecord):
    now = now_iso()
    incident_id = incident.id or f"egi-incident-{uuid.uuid4().hex[:8]}"
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO incidents
            (id, event_id, kind, title, description, lat, lon, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id, incident.event_id, incident.kind, incident.title,
                incident.description, incident.lat, incident.lon,
                incident.createdAt or now, incident.updatedAt or now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        return db.row_to_dict(row)


@app.get("/persons/{person_id}/reports")
def list_person_reports(person_id: str):
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE person_id = ? ORDER BY created_at DESC",
            (person_id,),
        ).fetchall()
        return {"records": [db.row_to_dict(r) for r in rows]}


@app.post("/persons/{person_id}/reports")
def create_person_report(person_id: str, report: ReportRecord):
    """Create a report (PFIF note) for a person. person_id comes from the path."""
    if not validate_status(report.status):
        raise HTTPException(status_code=400, detail=f"invalid status: {report.status}")
    now = now_iso()
    report.person_id = person_id
    report.id = report.id or f"egi-report-{uuid.uuid4().hex[:8]}"
    report.createdAt = report.createdAt or now
    report.updatedAt = report.updatedAt or now
    with db.get_db() as conn:
        cur = conn.cursor()
        _upsert_report(cur, report, now)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report.id,)
        ).fetchone()
        return db.row_to_dict(row)


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
