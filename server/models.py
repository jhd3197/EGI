"""Central Pydantic models and shared status/time helpers for the EGI server.

Field-name note (unchanged contract): person/report records use camelCase
``createdAt``/``updatedAt`` in JSON but snake_case ``created_at``/``updated_at``
in SQLite; the sync layer maps between them explicitly. PFIF and mesh-provenance
fields (``given_name``, ``cedula``, ``origin_device``, …) are snake_case in BOTH
JSON and DB (no mapping).
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel

# Valid person/report status values. Kept in sync with the SQLite CHECK in
# db.py and the status description in ocr.py's ExtractedPaperReport.
VALID_STATUSES = {"missing", "found", "safe", "deceased", "sighted", "care"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_ts(ts: Optional[str]) -> Optional[str]:
    """Normalize an ISO-8601 timestamp to a canonical UTC ``Z`` form.

    Last-write-wins compares timestamps lexicographically, which only matches the
    chronological order when every timestamp shares one representation. A mesh
    relay may send ``2026-01-01T00:00:00+00:00`` while the cloud stored
    ``2026-01-01T00:00:00Z`` — the SAME instant that sorts differently as text.
    We parse and re-emit in UTC with a ``Z`` suffix so equal instants compare
    equal. Unparseable input is returned unchanged (best-effort, never raises).
    """
    if not ts:
        return ts
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return ts


def validate_status(status: Optional[str]) -> bool:
    return status in VALID_STATUSES or status is None


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
