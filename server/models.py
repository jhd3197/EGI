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


# Trust tiers carried on a record (plan-25 Phase 1), highest → lowest. Computed
# server-side in modules/trust.py; kept here so the value set is centralized.
VALID_TRUST_TIERS = ("high", "medium", "low")


def validate_trust_tier(tier: Optional[str]) -> bool:
    return tier in VALID_TRUST_TIERS or tier is None


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
    # Raw-source provenance (plan-24.5): links to import_batches.
    import_batch_id: Optional[str] = None
    # Fuzzy-dedup: canonical id this record was merged into (null = not merged).
    merged_into: Optional[str] = None
    # Geospatial last-seen coordinates (plan-10). snake_case in BOTH JSON and DB.
    lat: Optional[float] = None
    lon: Optional[float] = None
    # Trust signals that travel with the record (plan-25 Phase 1). snake_case in
    # BOTH JSON and DB. author_role/org_id/location_id/signature are client-carried
    # provenance; trust_tier is COMPUTED server-side on upsert (modules/trust.py)
    # and never trusted from the client.
    author_role: Optional[str] = None
    org_id: Optional[str] = None
    location_id: Optional[str] = None
    signature: Optional[str] = None
    trust_tier: Optional[str] = None
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
    # Raw-source provenance (plan-24.5): links to import_batches.
    import_batch_id: Optional[str] = None
    # Confidence tier of the observation: self|official|witness|ocr. Drives the
    # person's derived status. snake_case in BOTH JSON and DB (no camel mapping).
    confidence: Optional[str] = None
    # Geospatial coordinates of the observation (plan-10).
    lat: Optional[float] = None
    lon: Optional[float] = None
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


# ── Communications hub (plan-11) ─────────────────────────────────────────────
#
# A unified messaging layer: SMS, email and push share one `messages` table and
# one delivery-status lifecycle. Provider config lives in `message_providers`.

VALID_CHANNELS = {"sms", "email", "push", "whatsapp", "telegram"}
VALID_DIRECTIONS = {"inbound", "outbound"}
# Delivery lifecycle. Kept in sync with the SQLite CHECK on messages.status.
VALID_MESSAGE_STATUSES = {"pending", "sent", "delivered", "failed", "bounced"}
VALID_PUSH_KINDS = {"webpush", "fcm"}


def validate_channel(channel: Optional[str]) -> bool:
    return channel in VALID_CHANNELS


def validate_message_status(status: Optional[str]) -> bool:
    return status in VALID_MESSAGE_STATUSES or status is None


class ProviderConfig(BaseModel):
    """A pluggable messaging provider row (SMS/email/push)."""

    id: Optional[str] = None
    channel: Optional[str] = None
    name: Optional[str] = None
    # Free-form provider settings (driver name, sender id, …). Secrets should
    # come from env, not here; this is for non-secret routing config.
    config: Optional[dict] = None
    is_default: Optional[int] = 0
    active: Optional[int] = 1


class SendMessageRequest(BaseModel):
    """Queue a single outbound message (templated or raw)."""

    channel: Optional[str] = None
    to_address: Optional[str] = None
    person_id: Optional[str] = None
    operation_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    template_name: Optional[str] = None
    # Variables for template rendering (operation name, person name, status, …).
    variables: Optional[dict] = None
    locale: Optional[str] = None

    @field_validator("subject")
    @classmethod
    def _clean_subject(cls, v):
        return clean_text(v, MAX_SHORT)

    @field_validator("body")
    @classmethod
    def _clean_body(cls, v):
        return clean_text(v, MAX_TEXT)


class BroadcastRequest(BaseModel):
    """Broadcast one SMS body to a list of phone numbers (by operation)."""

    operation_id: Optional[str] = None
    body: Optional[str] = None
    template_name: Optional[str] = None
    variables: Optional[dict] = None
    to_addresses: List[str] = []
    locale: Optional[str] = None

    @field_validator("body")
    @classmethod
    def _clean_body(cls, v):
        return clean_text(v, MAX_TEXT)


class AlertCreate(BaseModel):
    """Broadcast an alert to all subscribed channels of an operation (plan-11 §3)."""

    title: Optional[str] = None
    body: Optional[str] = None
    template_name: Optional[str] = None
    variables: Optional[dict] = None
    # Restrict to a subset of channels; default = all of sms/email/push.
    channels: Optional[List[str]] = None
    locale: Optional[str] = None
    # Life-safety override (plan-24 Phase 7): when set, a commander's broadcast
    # bypasses recipients' notification preferences so it always reaches them.
    life_safety: Optional[bool] = False

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("body")
    @classmethod
    def _clean_body(cls, v):
        return clean_text(v, MAX_TEXT)


class PushSubscribeRequest(BaseModel):
    """Register a Web-Push (VAPID) endpoint or an Android FCM token."""

    kind: Optional[str] = "webpush"
    endpoint: Optional[str] = None
    # Web Push key material (from PushSubscription.getKey()).
    p256dh: Optional[str] = None
    auth: Optional[str] = None
    # Operation id to subscribe to (None = global / all operations).
    topic: Optional[str] = None
    locale: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    password: str


class MessageStatusUpdate(BaseModel):
    """Provider delivery-status callback (e.g. Twilio status webhook)."""

    status: Optional[str] = None
    external_id: Optional[str] = None
    error: Optional[str] = None


# ── Operational intelligence: scheduled SITREP reports (plan-13) ──────────────

VALID_REPORT_FORMATS = {"pdf", "html", "json"}


class ScheduledReportCreate(BaseModel):
    """Register a recurring SITREP report against an operation."""

    operation_id: Optional[str] = None
    name: Optional[str] = None
    format: Optional[str] = "html"
    # Coarse keyword interval (hourly|daily|weekly) or a raw cron string.
    schedule_cron: Optional[str] = "daily"
    # Comma-separated emails and/or webhook subscription ids.
    recipients: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v):
        return clean_text(v, MAX_NAME)


class ScheduledReportUpdate(BaseModel):
    active: Optional[bool] = None


# ── Shelter & refugee information hub (plan-20) ───────────────────────────────
#
# Shelters become first-class server records (capacity, services, contact, an
# official update feed, check-ins). `services`/`supply_needs`/`target_populations`
# are free-form code lists rendered as chips in the UI; we keep them open (not a
# CHECK enum) so a deployment can add a service without a schema change. The
# canonical UI code lists are documented here for reference.

# Reference vocabularies (the UI knows how to render these; unknown codes are
# shown verbatim). Kept open on purpose — do not enforce as a CHECK.
SHELTER_SERVICES = {
    "beds", "food", "water", "medical", "childcare", "pets",
    "accessibility", "charging", "internet",
}
SHELTER_SUPPLY_NEEDS = {
    "water", "food", "medicine", "blankets", "clothing", "hygiene",
    "diapers", "volunteers",
}
SHELTER_TARGET_POPULATIONS = {
    "minors", "elderly", "women", "pets", "lgbtq", "disabled",
}
VALID_SHELTER_TRUST = {"official", "volunteer", "crowd"}
VALID_UPDATE_ROLES = {"official", "volunteer", "system"}


class ShelterRecord(BaseModel):
    """A shelter / hospital with capacity, services and contact metadata."""

    id: Optional[str] = None
    disaster_id: Optional[str] = None
    name: Optional[str] = None
    kind: Optional[str] = "refugio"  # 'refugio' | 'hospital'
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    hours: Optional[str] = None
    capacity_total: Optional[int] = None
    capacity_available: Optional[int] = None
    beds_available: Optional[int] = None
    occupancy: Optional[int] = None
    accepting_new: Optional[int] = 1
    services: Optional[List[str]] = None
    supply_needs: Optional[List[str]] = None
    target_populations: Optional[List[str]] = None
    notes: Optional[str] = None
    source: Optional[str] = "web"
    trust: Optional[str] = "crowd"
    operator_user_id: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("address", "phone", "whatsapp", "email", "hours")
    @classmethod
    def _clean_short(cls, v):
        return clean_text(v, MAX_SHORT)

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


class ShelterCapacityUpdate(BaseModel):
    """Real-time capacity / availability patch for a shelter (plan-20 §7)."""

    capacity_total: Optional[int] = None
    capacity_available: Optional[int] = None
    beds_available: Optional[int] = None
    occupancy: Optional[int] = None
    accepting_new: Optional[int] = None
    supply_needs: Optional[List[str]] = None
    target_populations: Optional[List[str]] = None
    services: Optional[List[str]] = None


class ShelterUpdateCreate(BaseModel):
    """A new entry in a shelter's official feed (plan-20 §6)."""

    message: Optional[str] = None
    author_name: Optional[str] = None
    author_role: Optional[str] = None  # official | volunteer | system
    services_changed: Optional[dict] = None
    occupancy_delta: Optional[int] = None
    source: Optional[str] = "web"
    expires_at: Optional[str] = None
    createdAt: Optional[str] = None

    @field_validator("message")
    @classmethod
    def _clean_message(cls, v):
        return clean_text(v, MAX_TEXT)

    @field_validator("author_name")
    @classmethod
    def _clean_author(cls, v):
        return clean_text(v, MAX_NAME)


class ShelterCheckinCreate(BaseModel):
    """A lightweight "I am at this shelter" self-report (plan-20 §8)."""

    id: Optional[str] = None
    alias: Optional[str] = None
    person_id: Optional[str] = None
    note: Optional[str] = None
    source: Optional[str] = "web"
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("alias")
    @classmethod
    def _clean_alias(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


class ShelterTokenCreate(BaseModel):
    """Issue a one-time shelter-claim token (commander only, plan-20 §9)."""

    label: Optional[str] = None
    expires_at: Optional[str] = None

    @field_validator("label")
    @classmethod
    def _clean_label(cls, v):
        return clean_text(v, MAX_SHORT)


class ShelterClaimRequest(BaseModel):
    """Redeem a shelter-claim token to become the verified operator."""

    token: str


# ── Shareable routes (plan-21 Phase 5) ────────────────────────────────────────
#
# A route share is a victim/responder broadcasting "here is a usable path from A
# to B" so others can reuse it. `polyline` is an optional list of [lat,lon] pairs
# (stored as JSON TEXT, decoded on read). `mode` is walk|drive. The server
# computes a dedup_key to collapse near-identical re-shares; clients never send it.

VALID_ROUTE_MODES = {"walk", "drive"}


def validate_route_mode(mode: Optional[str]) -> bool:
    return mode in VALID_ROUTE_MODES or mode is None


class RouteShareRecord(BaseModel):
    """A shareable route create/upsert payload (plan-21 Phase 5).

    ``polyline`` is an optional list of ``[lat, lon]`` pairs tracing the path; it
    is stored as JSON TEXT and decoded back to a list on read. ``mode`` is coerced
    to walk|drive (anything else falls back to ``walk``).
    """

    id: Optional[str] = None
    disaster_id: Optional[str] = None
    origin_lat: Optional[float] = None
    origin_lon: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None
    dest_name: Optional[str] = None
    polyline: Optional[List[list]] = None
    mode: Optional[str] = "walk"
    author_alias: Optional[str] = None
    note: Optional[str] = None
    source: Optional[str] = "web"
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v):
        return v if v in VALID_ROUTE_MODES else "walk"

    @field_validator("dest_name", "author_alias")
    @classmethod
    def _clean_short(cls, v):
        return clean_text(v, MAX_SHORT)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


# ── Evacuation corridors (plan-21 Phase 6) ────────────────────────────────────
#
# An evacuation corridor is an OFFICIAL recommended path out of a danger area,
# rendered on the map (distinct from a crowd-sourced route share). `path` is an
# optional list of [lat,lon] pairs (stored as JSON TEXT, decoded on read); `bbox`
# is computed server-side, never trusted from the client. `status` is
# open|congested|closed and `mode` is drive|walk|transit; both are coerced to a
# safe default (open / drive) when an unknown value arrives.

VALID_CORRIDOR_STATUSES = {"open", "congested", "closed"}
VALID_CORRIDOR_MODES = {"drive", "walk", "transit"}


def validate_corridor_status(status: Optional[str]) -> bool:
    return status in VALID_CORRIDOR_STATUSES or status is None


def validate_corridor_mode(mode: Optional[str]) -> bool:
    return mode in VALID_CORRIDOR_MODES or mode is None


class CorridorRecord(BaseModel):
    """An evacuation-corridor create/upsert payload (plan-21 Phase 6).

    ``path`` is an optional list of ``[lat, lon]`` pairs tracing the corridor; it
    is stored as JSON TEXT and decoded back to a list on read. ``status`` is
    coerced to open|congested|closed (default ``open``) and ``mode`` to
    drive|walk|transit (default ``drive``).
    """

    id: Optional[str] = None
    disaster_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = "open"
    mode: Optional[str] = "drive"
    path: Optional[List[list]] = None
    note: Optional[str] = None
    source: Optional[str] = "official"
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        # Reject an out-of-range status (422) rather than silently coercing — the
        # SQLite CHECK constraint would reject it too, and a wrong corridor status
        # ("closed" vs "open") is safety-relevant, so fail loudly.
        if v is None:
            return "open"
        if v not in VALID_CORRIDOR_STATUSES:
            raise ValueError(f"invalid corridor status: {v!r}")
        return v

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v):
        return v if v in VALID_CORRIDOR_MODES else "drive"

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


# ── Hazard zones (plan-21 Phase 4) ────────────────────────────────────────────
#
# A hazard zone is a flagged danger area (flood/landslide/fire/blocked road/unsafe
# zone) with a polygon or circle geometry. Offline routing can avoid them and the
# map renders them; community reports land as untrusted (`hazard_report`,
# reviewed=0) and await moderation, while operator/official submissions are trusted
# (reviewed=1). The server computes a `bbox` for cheap overlap filtering.

VALID_HAZARD_TYPES = {"flood", "landslide", "fire", "blocked_road", "unsafe_zone"}
VALID_HAZARD_CONFIDENCE = {"low", "medium", "high"}


def validate_hazard_type(hazard_type: Optional[str]) -> bool:
    return hazard_type in VALID_HAZARD_TYPES


class HazardRecord(BaseModel):
    """A hazard-zone create/upsert payload (plan-21 Phase 4).

    ``geometry`` is a free-form dict matching the wire contract:
    ``{"kind":"polygon","coords":[[lat,lon],...]}`` or
    ``{"kind":"circle","center":[lat,lon],"radius_m":N}``. ``bbox`` is computed
    server-side, never trusted from the client.
    """

    id: Optional[str] = None
    disaster_id: Optional[str] = None
    type: Optional[str] = None
    geometry: Optional[dict] = None
    active_from: Optional[str] = None
    active_until: Optional[str] = None
    source: Optional[str] = "web"
    confidence: Optional[str] = None
    reviewed: Optional[int] = 0
    reporter_name: Optional[str] = None
    note: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("reporter_name")
    @classmethod
    def _clean_reporter(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


# ── User preferences, subscriptions & alerts (plan-24) ────────────────────────
#
# A unified layer so each user controls what they SEE (display), what NOTIFIES
# them (notify), and what they RELAY over the mesh (mesh_relay) per content
# category. Categories are extensible: a new module only registers a category
# string + UI strings. Defaults live in modules/preferences.py; an absent row
# means "use the default", so we only persist what the user has changed.

# Content categories (broad buckets of information). Kept in sync with the
# CATEGORIES list in frontend/src/lib/preferences.js.
CONTENT_CATEGORIES = {
    "people",
    "animals",
    "shelters",
    "hazards",
    "supplies",
    "operations",
    "broadcasts",
}

# Categories whose notifications are ON by default. Other categories default to
# display + mesh-relay on, but notifications off, to keep the alert channel quiet.
DEFAULT_NOTIFY_CATEGORIES = {"people", "broadcasts"}

# Life-safety categories: a user may turn these down, but own-record matches and
# commander life-safety broadcasts bypass the toggle (plan-24 Phase 7). Used by
# the notification guardrails, not enforced here at the model layer.
CRITICAL_CATEGORIES = {"people", "broadcasts"}


def validate_category(category: Optional[str]) -> bool:
    return category in CONTENT_CATEGORIES


class CategoryPreference(BaseModel):
    """One category's display/notify/relay toggles for a user (plan-24 Phase 1)."""

    category: str
    display_enabled: Optional[int] = 1
    notify_enabled: Optional[int] = None  # None → category default
    mesh_relay_enabled: Optional[int] = 1
    radius_meters: Optional[int] = None  # per-category "near me" override
    updated_at: Optional[str] = None

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v):
        if not validate_category(v):
            raise ValueError(f"unknown content category: {v!r}")
        return v


class UserSettings(BaseModel):
    """Per-user global (non-category) settings (plan-24 Phase 1)."""

    radius_meters: Optional[int] = None  # global "near me" radius in metres
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    quiet_hours_start: Optional[int] = None  # hour 0-23
    quiet_hours_end: Optional[int] = None
    batch_notifications: Optional[int] = 0
    updated_at: Optional[str] = None


class PreferencesUpdate(BaseModel):
    """Patch a user's category preferences and/or global settings (plan-24)."""

    categories: Optional[List[CategoryPreference]] = None
    settings: Optional[UserSettings] = None


class OperationSubscriptionUpdate(BaseModel):
    """Subscribe to / mute an operation for a user (plan-24 Phase 6)."""

    operation_id: str
    muted: Optional[int] = 0
    updated_at: Optional[str] = None


# ── Trust, safety & verification (plan-25) ──────────────────────────────────

class OrgCreate(BaseModel):
    """Create an organization (plan-25 Phase 2)."""

    name: str
    kind: Optional[str] = None
    description: Optional[str] = None
    public_key: Optional[str] = None


class OrgMemberAdd(BaseModel):
    user_id: str
    role: Optional[str] = "member"


class OrgKeyPin(BaseModel):
    public_key: str


class LocationCreate(BaseModel):
    """Create an authorization location — hospital/shelter/water point (Phase 2)."""

    name: str
    kind: Optional[str] = None
    org_id: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class WatcherAdd(BaseModel):
    user_id: str
    expires_at: Optional[str] = None


class InviteCreate(BaseModel):
    """Mint an org/location invite (Phase 2). target_type is set by the route."""

    grant_role: Optional[str] = None
    label: Optional[str] = None
    expires_at: Optional[str] = None


class InviteRedeem(BaseModel):
    token: str


class FlagCreate(BaseModel):
    """Report a concern about a record (plan-25 Phase 3)."""

    record_type: str
    record_id: str
    flag_reason: Optional[str] = None
    note: Optional[str] = None
    flagged_by: Optional[str] = None
    origin_device: Optional[str] = None


class FlagResolve(BaseModel):
    status: str  # 'resolved' | 'dismissed'
    resolution: Optional[str] = None


class ModeratorSignup(BaseModel):
    """Diaspora moderator onboarding (plan-25 Phase 4)."""

    display_name: Optional[str] = None
    languages: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    invite_token: Optional[str] = None


# ── Search & Rescue operations workflow (plan-26) ────────────────────────────
#
# Lightweight civilian SAR coordination layered over the registry. Namespaced
# `sar_*` so it never collides with the plan-09 operations (events) surface. The
# status sets below are enforced at the app layer (no SQLite CHECK on the additive
# columns, same rationale as the operations status set above).

VALID_SAR_OPERATION_STATUSES = {"active", "paused", "closed"}
VALID_SECTOR_STATUSES = {
    "unassigned", "assigned", "in_progress", "cleared", "needs_recheck",
}
VALID_FIELD_REPORT_TYPES = {
    "sighting", "cleared", "needs_help", "found",
    # plan-27.5: a hospital/shelter match (Phase 4) and a building inspection
    # (Phase 5) are first-class field reports that flow over the same mesh/cloud.
    "facility_match", "building_inspection",
}
# Facility-match verdicts (plan-27.5 Phase 4). Carried in the field report's
# structured `details` JSON. `person_is_here` is a strong lead that, once a
# coordinator confirms, can update the person record.
VALID_FACILITY_MATCH_VERDICTS = {"person_is_here", "person_not_here", "needs_verification"}
VALID_VOLUNTEER_STATUSES = {"joined", "checked_in", "checked_out"}

# Reference task vocabulary (the UI renders these; unknown codes shown verbatim).
# Kept open on purpose — do not enforce as a CHECK.
SAR_TASK_KINDS = {
    "search_foot", "ask_neighbors", "check_shelters", "post_flyers",
    "verify_sighting", "escort_found", "custom",
}


def validate_sar_operation_status(status: Optional[str]) -> bool:
    return status in VALID_SAR_OPERATION_STATUSES or status is None


def validate_sector_status(status: Optional[str]) -> bool:
    return status in VALID_SECTOR_STATUSES or status is None


def validate_field_report_type(t: Optional[str]) -> bool:
    return t in VALID_FIELD_REPORT_TYPES


class SectorCreate(BaseModel):
    """One sector defined manually when creating/updating an operation."""

    name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_m: Optional[int] = None
    bbox: Optional[List[float]] = None  # [minLon, minLat, maxLon, maxLat]
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v):
        return clean_text(v, MAX_SHORT)

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


class SarOperationCreate(BaseModel):
    """Create a SAR operation (plan-26 Phase 1).

    Either a list of linked missing persons, a search zone, or both. When
    ``auto_grid`` (>1) is set with a zone, the server splits the zone's bounding
    box into an ``auto_grid``×``auto_grid`` grid of sectors; otherwise ``sectors``
    (if any) are created verbatim.
    """

    id: Optional[str] = None
    disaster_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = "active"
    zone_lat: Optional[float] = None
    zone_lon: Optional[float] = None
    zone_radius_m: Optional[int] = None
    person_ids: Optional[List[str]] = None
    sectors: Optional[List[SectorCreate]] = None
    auto_grid: Optional[int] = None  # NxN grid of sectors over the zone bbox
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("description")
    @classmethod
    def _clean_desc(cls, v):
        return clean_text(v, MAX_TEXT)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v is None:
            return "active"
        if v not in VALID_SAR_OPERATION_STATUSES:
            raise ValueError(f"invalid operation status: {v!r}")
        return v


class SarOperationUpdate(BaseModel):
    """Patch an operation's mutable fields (plan-26)."""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    zone_lat: Optional[float] = None
    zone_lon: Optional[float] = None
    zone_radius_m: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("description")
    @classmethod
    def _clean_desc(cls, v):
        return clean_text(v, MAX_TEXT)


class SarOperationStatusUpdate(BaseModel):
    """PATCH /sar/operations/{id}/status body."""

    status: str
    reason: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v not in VALID_SAR_OPERATION_STATUSES:
            raise ValueError(f"invalid operation status: {v!r}")
        return v

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, v):
        return clean_text(v, MAX_TEXT)


class SectorStatusUpdate(BaseModel):
    """Change a sector's status / notes (plan-26 Phase 3)."""

    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v is not None and v not in VALID_SECTOR_STATUSES:
            raise ValueError(f"invalid sector status: {v!r}")
        return v

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


class SectorClaim(BaseModel):
    """Claim (or release) a sector as a volunteer (plan-26 Phase 3)."""

    alias: Optional[str] = None
    volunteer_id: Optional[str] = None
    device_id: Optional[str] = None

    @field_validator("alias")
    @classmethod
    def _clean_alias(cls, v):
        return clean_text(v, MAX_NAME)


class SarTaskCreate(BaseModel):
    """Add a checklist task to an operation or a sector (plan-26 Phase 3)."""

    title: Optional[str] = None
    kind: Optional[str] = "custom"
    sector_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


class SarTaskUpdate(BaseModel):
    """Mark a task done / edit its note (plan-26 Phase 3)."""

    done: Optional[bool] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    completed_by: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)


class VolunteerJoin(BaseModel):
    """A user/device joins an operation (plan-26 Phase 2/3).

    ``role`` is the volunteer's "hat" (plan-27.5 Phase 3) — it only changes what
    the app surfaces first and is never a hard gate. Open vocabulary
    (VALID_VOLUNTEER_ROLES); an unknown code is rejected to keep the data clean.
    """

    alias: Optional[str] = None
    device_id: Optional[str] = None
    role: Optional[str] = None

    @field_validator("alias")
    @classmethod
    def _clean_alias(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v):
        if v is not None and v not in VALID_VOLUNTEER_ROLES:
            raise ValueError(f"invalid role: {v!r}")
        return v


class VolunteerRoleUpdate(BaseModel):
    """Change a volunteer's role without leaving the operation (plan-27.5 P3)."""

    role: str

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v):
        if v not in VALID_VOLUNTEER_ROLES:
            raise ValueError(f"invalid role: {v!r}")
        return v


class VolunteerCheckin(BaseModel):
    """Check a volunteer in/out of a sector (plan-26 Phase 3)."""

    volunteer_id: str
    sector_id: Optional[str] = None


class FieldReportCreate(BaseModel):
    """A field report filed by a volunteer (plan-26 Phase 4).

    Created offline and synced via mesh/cloud (timestamp-guarded LWW on ``id``).
    ``type`` is sighting|cleared|needs_help|found. A ``found`` report can update
    the linked person's registry status, but only after confirmation (Phase 6).
    """

    id: Optional[str] = None
    operation_id: Optional[str] = None
    sector_id: Optional[str] = None
    person_id: Optional[str] = None
    type: Optional[str] = None
    note: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    photo_url: Optional[str] = None
    reporter_alias: Optional[str] = None
    origin_device: Optional[str] = None
    source: Optional[str] = "web"
    # Report-type-specific structured payload (plan-27.5): the building-inspection
    # checklist (Phase 5) or the facility-match {"verdict": …} (Phase 4). Stored
    # in the `checklist` JSON column.
    checklist: Optional[dict] = None
    facility_id: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v):
        if v is not None and v not in VALID_FIELD_REPORT_TYPES:
            raise ValueError(f"invalid field-report type: {v!r}")
        return v

    @field_validator("reporter_alias")
    @classmethod
    def _clean_alias(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


class FieldReportResolve(BaseModel):
    """Confirm or dismiss a field report (plan-26 Phase 6)."""

    confirmed: bool
    # When confirming a `found` report, optionally set the person's new status.
    person_status: Optional[str] = None

    @field_validator("person_status")
    @classmethod
    def _validate_person_status(cls, v):
        if v is not None and not validate_status(v):
            raise ValueError(f"invalid status: {v!r}")
        return v


class SarSyncPayload(BaseModel):
    """Upload half of SAR mesh/cloud sync: field reports created offline."""

    field_reports: List[FieldReportCreate] = []


class FacilityWatchCreate(BaseModel):
    """A facility watcher subscribes a facility to a SAR operation (plan-27.5 P4)."""

    facility_id: str


class FacilityMatchCreate(BaseModel):
    """A hospital/shelter watcher's verdict on a linked missing person (P4).

    ``verdict`` is person_is_here|person_not_here|needs_verification. It becomes a
    ``facility_match`` field report on the operation; a ``person_is_here`` verdict
    is a strong lead a coordinator can confirm to update the person record.
    """

    facility_id: str
    person_id: str
    verdict: str
    note: Optional[str] = None

    @field_validator("verdict")
    @classmethod
    def _validate_verdict(cls, v):
        if v not in VALID_FACILITY_MATCH_VERDICTS:
            raise ValueError(f"invalid facility-match verdict: {v!r}")
        return v

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v):
        return clean_text(v, MAX_TEXT)


# ── Volunteer registry (plan-27.5 Phase 1) ────────────────────────────────────

VALID_VOLUNTEER_AVAILABILITY = {"available", "busy", "on_call", "unavailable"}
VALID_VOLUNTEER_MOBILITY = {"local", "remote", "mobile"}

# Role "hats" a volunteer can wear (plan-27.5 §4.1). Open vocabulary — the UI
# surfaces these but unknown codes are shown verbatim, so this is NOT a CHECK.
VALID_VOLUNTEER_ROLES = {
    "person_looking", "field_volunteer", "local_guide", "remote_watcher",
    "specialist", "coordinator", "facility_watcher",
}


def validate_volunteer_availability(v: Optional[str]) -> bool:
    return v is None or v in VALID_VOLUNTEER_AVAILABILITY


def validate_volunteer_mobility(v: Optional[str]) -> bool:
    return v is None or v in VALID_VOLUNTEER_MOBILITY


class VolunteerProfileWrite(BaseModel):
    """Create or update a volunteer profile (plan-27.5 Phase 1).

    Every field is optional so a profile can grow over time. ``languages`` and
    ``skills`` are free lists; ``availability``/``mobility`` are validated against
    the small vocabularies above. ``device_id`` keys the PWA's anonymous guest
    flow when there is no account.
    """

    id: Optional[str] = None
    device_id: Optional[str] = None
    display_name: Optional[str] = None
    contact: Optional[str] = None
    region: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    languages: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    availability: Optional[str] = None
    mobility: Optional[str] = None
    visible: Optional[bool] = None
    notes: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    @field_validator("display_name", "contact", "region")
    @classmethod
    def _clean_short(cls, v):
        return clean_text(v, MAX_NAME)

    @field_validator("notes")
    @classmethod
    def _clean_notes(cls, v):
        return clean_text(v, MAX_TEXT)

    @field_validator("availability")
    @classmethod
    def _validate_availability(cls, v):
        if v is not None and v not in VALID_VOLUNTEER_AVAILABILITY:
            raise ValueError(f"invalid availability: {v!r}")
        return v

    @field_validator("mobility")
    @classmethod
    def _validate_mobility(cls, v):
        if v is not None and v not in VALID_VOLUNTEER_MOBILITY:
            raise ValueError(f"invalid mobility: {v!r}")
        return v

    @field_validator("languages", "skills")
    @classmethod
    def _clean_list(cls, v):
        if v is None:
            return None
        out = []
        for item in v:
            cleaned = clean_text(item, MAX_SHORT)
            if cleaned:
                out.append(cleaned)
        return out[:30]  # cap so a fat-fingered list can't explode
