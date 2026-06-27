"""Central Pydantic models and shared status/time helpers for the EGI server.

Field-name note (unchanged contract): person/report records use camelCase
``createdAt``/``updatedAt`` in JSON but snake_case ``created_at``/``updated_at``
in SQLite; the sync layer maps between them explicitly. PFIF and mesh-provenance
fields (``given_name``, ``cedula``, ``origin_device``, …) are snake_case in BOTH
JSON and DB (no mapping).
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, field_validator

from validators import MAX_NAME, MAX_SHORT, MAX_TEXT, clean_text

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


# Report confidence tiers (highest → lowest). Kept in sync with
# modules/confidence.py CONFIDENCE_RANK.
VALID_CONFIDENCE = {"self", "official", "witness", "ocr"}


def validate_confidence(confidence: Optional[str]) -> bool:
    return confidence in VALID_CONFIDENCE or confidence is None


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
    # Fuzzy-dedup: canonical id this record was merged into (null = not merged).
    merged_into: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    # Length-limit + HTML-strip the free-text fields (defense in depth; §12.1).
    @field_validator("name", "given_name", "family_name", "reporter_name")
    @classmethod
    def _clean_names(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator(
        "location", "last_known_location", "clothes", "contact",
        "reporter_relation", "reporter_country", "reported_by",
    )
    @classmethod
    def _clean_short(cls, v):
        return clean_text(v, MAX_SHORT)

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


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
    # Confidence tier of the observation: self|official|witness|ocr. Drives the
    # person's derived status. snake_case in BOTH JSON and DB (no camel mapping).
    confidence: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("author_name", "author_relation")
    @classmethod
    def _clean_author(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("note", "location")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


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


# ── Operations / action plans / tasks (plan-09) ──────────────────────────────
#
# An "operation" is an `events` row promoted to an active operational case. Its
# operational status set is enforced here (not by a SQLite CHECK; see db.py). The
# task state machine mirrors the CHECK on action_plan_tasks.state.

VALID_OPERATION_STATUSES = {"open", "paused", "closed"}
VALID_TASK_STATES = {"pending", "in_progress", "done", "cancelled"}


def validate_operation_status(status: Optional[str]) -> bool:
    return status in VALID_OPERATION_STATUSES or status is None


def validate_task_state(state: Optional[str]) -> bool:
    return state in VALID_TASK_STATES or state is None


class OperationCreate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    type: Optional[str] = None
    tag: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = "open"
    commander_id: Optional[str] = None
    is_practice: Optional[int] = 0
    started_at: Optional[str] = None
    utm_x: Optional[float] = None
    utm_y: Optional[float] = None
    municipality: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None

    @field_validator("name", "contact_person")
    @classmethod
    def _clean_op_names(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("region", "type", "tag", "municipality", "contact_phone")
    @classmethod
    def _clean_op_short(cls, v):
        return clean_text(v, MAX_SHORT)


class OperationUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    type: Optional[str] = None
    tag: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None
    commander_id: Optional[str] = None
    is_practice: Optional[int] = None
    utm_x: Optional[float] = None
    utm_y: Optional[float] = None
    municipality: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None

    @field_validator("name", "contact_person")
    @classmethod
    def _clean_op_names(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("region", "type", "tag", "municipality", "contact_phone")
    @classmethod
    def _clean_op_short(cls, v):
        return clean_text(v, MAX_SHORT)


class OperationClose(BaseModel):
    reason: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, v):
        return clean_text(v, MAX_TEXT)


class ActionPlanCreate(BaseModel):
    description: Optional[str] = None
    # When true, copy the previous version's tasks instead of seeding templates.
    copy_from_previous: Optional[bool] = False
    # When true (default), seed default task templates into the new plan.
    seed_defaults: Optional[bool] = True

    @field_validator("description")
    @classmethod
    def _clean_desc(cls, v):
        return clean_text(v, MAX_TEXT)


class ActionPlanUpdate(BaseModel):
    description: Optional[str] = None

    @field_validator("description")
    @classmethod
    def _clean_desc(cls, v):
        return clean_text(v, MAX_TEXT)


class TaskCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    state: Optional[str] = "pending"
    sort_order: Optional[int] = 0
    notes: Optional[str] = None
    due_at: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("description", "notes")
    @classmethod
    def _clean_text(cls, v):
        return clean_text(v, MAX_TEXT)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    state: Optional[str] = None
    sort_order: Optional[int] = None
    notes: Optional[str] = None
    due_at: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("description", "notes")
    @classmethod
    def _clean_text(cls, v):
        return clean_text(v, MAX_TEXT)


class TaskSyncRecord(BaseModel):
    """A field-originated task state change pushed back to the server (plan-09 §8).

    Only the mutable, field-relevant columns travel; the task must already exist
    server-side (plans/tasks are server-created). Last-write-wins on ``updatedAt``.
    """

    id: str
    state: Optional[str] = None
    assignee_id: Optional[str] = None
    notes: Optional[str] = None
    completed_at: Optional[str] = None
    completed_by: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


class OperationSyncPayload(BaseModel):
    """Upload half of the operations sync: a batch of task state changes."""

    tasks: List[TaskSyncRecord] = []


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
