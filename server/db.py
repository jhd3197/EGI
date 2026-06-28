import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = Path(os.environ.get("DB_PATH", "./data/egi.db")).resolve()


def database_url() -> str:
    """The configured ``DATABASE_URL`` (empty string when on the SQLite default).

    PostgreSQL is opt-in via ``DATABASE_URL=postgresql://…`` (plan-15 §7). When
    empty, EGI uses the local SQLite file at ``DB_PATH`` — the default for every
    small community deployment.
    """
    return os.environ.get("DATABASE_URL", "").strip()


def is_postgres() -> bool:
    """True when EGI is configured to run against PostgreSQL."""
    return database_url().lower().startswith(("postgres://", "postgresql://"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    name TEXT,
    status TEXT CHECK(status IN ('missing','found','safe','deceased','sighted','care')),
    gender TEXT,
    age INTEGER,
    location TEXT,
    last_seen_date TEXT,
    clothes TEXT,
    notes TEXT,
    contact TEXT,
    reporter_name TEXT,
    reporter_relation TEXT,
    reporter_country TEXT,
    reported_by TEXT,
    source TEXT DEFAULT 'web',
    provenance TEXT,
    image_path TEXT,
    ocr_text TEXT,
    extracted_json TEXT,
    confidence REAL,
    reviewed INTEGER DEFAULT 0,
    given_name TEXT,
    family_name TEXT,
    cedula TEXT,
    sex TEXT,
    photo_url TEXT,
    last_known_location TEXT,
    origin_device TEXT,
    hop_count INTEGER DEFAULT 0,
    merged_into TEXT,
    -- Geospatial last-seen coordinates (plan-10). Optional; free-text `location`
    -- stays the human-readable label. Indexed below for radius/bbox search.
    lat REAL,
    lon REAL,
    import_batch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_persons_disaster ON persons(disaster_id);
CREATE INDEX IF NOT EXISTS idx_persons_status ON persons(status);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_location ON persons(location);
CREATE INDEX IF NOT EXISTS idx_persons_updated_at ON persons(updated_at);
CREATE INDEX IF NOT EXISTS idx_persons_source ON persons(source);
CREATE INDEX IF NOT EXISTS idx_persons_batch ON persons(import_batch_id);

-- PFIF-aligned tables. All additive; loosely coupled to persons by id references.
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    name TEXT,
    region TEXT,
    type TEXT,
    tag TEXT,
    date TEXT,
    status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    name TEXT,
    region TEXT,
    lat REAL,
    lon REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cities_event ON cities(event_id);

-- PFIF "note" concept: a report/observation attached to a person.
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    person_id TEXT,
    author_name TEXT,
    author_relation TEXT,
    status TEXT,
    note TEXT,
    location TEXT,
    source TEXT DEFAULT 'web',
    origin_device TEXT,
    confidence TEXT,
    -- Geospatial coordinates of the observation (plan-10). Optional.
    lat REAL,
    lon REAL,
    import_batch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_person ON reports(person_id);
CREATE INDEX IF NOT EXISTS idx_reports_batch ON reports(import_batch_id);

-- Raw-source provenance (plan-24.5). One row per uploaded/ingested raw source.
-- Server-local; not synced over the mesh. Records in persons/reports link here
-- via import_batch_id so operators can trace a record back to its file, hash,
-- extraction method and batch mates.
CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    source_type TEXT NOT NULL,
    original_filename TEXT,
    stored_filename TEXT,
    file_hash TEXT,
    file_size INTEGER,
    media_type TEXT,
    extraction_method TEXT,
    record_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','processed','partial','failed')),
    error_log TEXT,
    uploaded_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_import_batches_disaster ON import_batches(disaster_id);
CREATE INDEX IF NOT EXISTS idx_import_batches_hash ON import_batches(file_hash);
CREATE INDEX IF NOT EXISTS idx_import_batches_source_type ON import_batches(source_type);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    kind TEXT,
    title TEXT,
    description TEXT,
    lat REAL,
    lon REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_event ON incidents(event_id);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT,
    peer TEXT,
    origin_device TEXT,
    record_count INTEGER,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- Fuzzy-dedup: moderator decisions that two persons are NOT duplicates. Stored as
-- a sorted id pair so a rejected cluster is never suggested again.
CREATE TABLE IF NOT EXISTS dedup_rejections (
    id_a TEXT NOT NULL,
    id_b TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (id_a, id_b)
);

-- Audit log: attributable operator actions and auth events (plan-07 §8). Append
-- only; never stores full tokens (the `actor` is a short non-secret principal).
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT,
    action TEXT,
    target_type TEXT,
    target_id TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- Record history: append-only change trail for a person record (who/what/when).
-- Captures create/update/merge so a record's evolution is reconstructable.
CREATE TABLE IF NOT EXISTS record_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    actor TEXT,
    change TEXT,
    source TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_person ON record_history(person_id);

-- User accounts + opaque bearer tokens (plan-08). Replaces the static
-- OPERATOR_TOKENS env var with real, role-scoped accounts. Passwords are stored
-- only as bcrypt hashes; tokens only as SHA-256 hashes, so the DB never holds a
-- usable credential. `active=0` disables a user without deleting their history.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    role TEXT NOT NULL CHECK(role IN ('viewer','operator','commander','admin')),
    password_hash TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    last_login_at TEXT,
    last_login_ip TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Opaque bearer tokens. `token_hash` is SHA-256(raw token); the raw token is
-- shown to the client exactly once at creation and never stored. Deleting a
-- user cascades to their tokens (immediate revocation).
CREATE TABLE IF NOT EXISTS user_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT,
    expires_at TEXT,
    last_used_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_tokens_user ON user_tokens(user_id);

-- Search operations & action plans (plan-09). The existing `events` table is
-- promoted from a passive PFIF metadata container into an active operational
-- "operation" case entity (extra columns added by idempotent migration below).
-- Each operation can hold multiple versioned action plans; only one is active.
CREATE TABLE IF NOT EXISTS action_plans (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 0,
    deleted INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    UNIQUE(event_id, version)
);

CREATE INDEX IF NOT EXISTS idx_action_plans_event ON action_plans(event_id);

CREATE TABLE IF NOT EXISTS action_plan_tasks (
    id TEXT PRIMARY KEY,
    action_plan_id TEXT NOT NULL,
    assignee_id TEXT REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    state TEXT DEFAULT 'pending' CHECK(state IN ('pending','in_progress','done','cancelled')),
    sort_order INTEGER DEFAULT 0,
    notes TEXT,
    due_at TEXT,
    completed_at TEXT,
    completed_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (action_plan_id) REFERENCES action_plans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_plan ON action_plan_tasks(action_plan_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON action_plan_tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON action_plan_tasks(updated_at);

-- Default task templates seeded into each new action plan. Stored in the DB
-- (not hard-coded) so a deployment can customize the seed list. Seeded once on
-- first init by `_seed_task_templates` when the table is empty.
CREATE TABLE IF NOT EXISTS task_templates (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Photos attached to a person (plan-10). High-risk crisis data: the stored file
-- name is a content hash, NOT the uploader's original filename, and the image is
-- resized + EXIF-stripped before storage (with GPS optionally lifted into
-- lat/lon first). A person can have many photos, so this is a side table rather
-- than the single `image_path`/`photo_url` columns on persons. Files are served
-- only through the operator-gated, ENABLE_PHOTOS-guarded /uploads route.
CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    uploader_id TEXT,
    filename_hash TEXT UNIQUE NOT NULL,  -- stored filename, not original
    thumbnail_hash TEXT,
    width INTEGER,
    height INTEGER,
    content_type TEXT,
    lat REAL,
    lon REAL,
    taken_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_photos_person ON photos(person_id);

-- Communications hub (plan-11): pluggable outbound/inbound messaging across SMS,
-- email and push. Provider config is a row here so switching from (e.g.) Twilio
-- to another SMS gateway is a config change, not a code change. `config_json`
-- holds provider-specific settings (API keys live in env, not here, by default).
CREATE TABLE IF NOT EXISTS message_providers (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL CHECK(channel IN ('sms','email','push','whatsapp','telegram')),
    name TEXT,
    config_json TEXT,
    is_default INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_providers_channel ON message_providers(channel);

-- Inclusive crisis access (plan-14): chatbot sessions + voice transcripts.
--
-- A chatbot session holds the multi-turn conversation state for one external
-- user on one channel (WhatsApp/Telegram). `current_draft_id` points at the
-- person record being assembled; `intent`/`state` drive the question flow so a
-- follow-up answer lands on the right field. UNIQUE(channel, external_user_id)
-- means one live conversation per phone/account. Server-local, never synced over
-- the mesh — it is transient conversational bookkeeping, not registry data.
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL CHECK(channel IN ('whatsapp','telegram')),
    external_user_id TEXT NOT NULL,
    current_draft_id TEXT,
    intent TEXT,
    state TEXT,
    language TEXT DEFAULT 'es',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(channel, external_user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_external ON chat_sessions(channel, external_user_id);

-- Voice transcripts attached to a draft/report (plan-14 §6). A voice note is
-- transcribed (on-device on Android, or a local Whisper fallback server-side)
-- and the resulting text is stored here with a confidence score, so a low-
-- confidence transcription can be flagged "please confirm" before it is trusted.
-- All voice-derived person records remain reviewed=0 (moderation) like any other
-- bot draft.
CREATE TABLE IF NOT EXISTS voice_transcripts (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    person_id TEXT,
    transcript TEXT NOT NULL,
    confidence REAL,
    language TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_voice_transcripts_person ON voice_transcripts(person_id);

-- Every message that flows through the hub (inbound + outbound), with a
-- per-message delivery-status lifecycle so a commander can see what was sent and
-- whether it landed. `external_id` is the provider's own id (for status callbacks).
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    operation_id TEXT,
    person_id TEXT,
    channel TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
    to_address TEXT,
    from_address TEXT,
    subject TEXT,
    body TEXT,
    template_name TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','sent','delivered','failed','bounced')),
    error TEXT,
    external_id TEXT,
    provider_id TEXT,
    alert_id TEXT,
    locale TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_person ON messages(person_id);
CREATE INDEX IF NOT EXISTS idx_messages_operation ON messages(operation_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_alert ON messages(alert_id);

-- Push subscriptions: a PWA Web-Push (VAPID) endpoint or an Android FCM token.
-- `topic` is the operation id the device subscribed to (NULL = global/all), so an
-- alert can fan out to every device watching one operation. `endpoint` is the
-- unique key for Web Push; for FCM the token is stored there too.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('webpush','fcm')),
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT,
    auth TEXT,
    topic TEXT,
    user_id TEXT,
    locale TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_push_topic ON push_subscriptions(topic);
CREATE INDEX IF NOT EXISTS idx_push_kind ON push_subscriptions(kind);

-- Password-reset tokens (plan-11 email). Stored only as SHA-256(token) like
-- user_tokens; the raw token travels by email and is shown nowhere else. Single
-- use: `used_at` is stamped on redemption.
CREATE TABLE IF NOT EXISTS password_resets (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);

-- Interoperability & federation (plan-12). Three additive tables; loosely coupled
-- to the rest of the schema. None are synced over the mesh — they are server-local
-- operator configuration + delivery/peer bookkeeping.

-- Outbound webhook subscriptions: an external system registers a URL + the event
-- types it cares about. `secret` (if set) signs each delivery (HMAC-SHA256) so the
-- receiver can verify authenticity. `events` is a comma-separated list of event
-- types (or '*' for all). Deactivate with active=0 rather than deleting to keep
-- the delivery history meaningful.
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    url TEXT NOT NULL,
    events TEXT NOT NULL,  -- comma-separated event types, or '*' for all
    secret TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_webhook_subs_active ON webhook_subscriptions(active);

-- Per-attempt webhook delivery log. One row per attempt (retries add rows), so a
-- failed-then-succeeded delivery is fully auditable. `success=0` rows with attempts
-- below the cap are eligible for redelivery by webhooks.retry_pending().
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL,
    event_type TEXT,
    payload TEXT,
    response_status INTEGER,
    response_body TEXT,
    attempt INTEGER DEFAULT 1,
    attempted_at TEXT NOT NULL,
    next_retry_at TEXT,
    success INTEGER DEFAULT 0,
    FOREIGN KEY (subscription_id) REFERENCES webhook_subscriptions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_sub ON webhook_deliveries(subscription_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_pending
    ON webhook_deliveries(success, next_retry_at);

-- Trusted peer EGI servers for server-to-server federation. `public_key` is pinned
-- at registration (TOFU); federation pulls/pushes records since `last_sync_at`
-- reusing the existing /sync last-write-wins logic. `token` (if set) is sent as the
-- bearer credential when calling the peer's authenticated endpoints.
CREATE TABLE IF NOT EXISTS trusted_peers (
    id TEXT PRIMARY KEY,
    name TEXT,
    base_url TEXT NOT NULL,
    public_key TEXT,
    token TEXT,
    last_sync_at TEXT,
    last_push_at TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trusted_peers_active ON trusted_peers(active);

-- Operational intelligence (plan-13). Two additive, server-local tables.

-- Per-record data-quality score (plan-13 §4). A cached, recomputable snapshot of
-- how trustworthy/complete a person record is (0-100), broken into the
-- completeness / confidence / freshness sub-scores and a JSON list of issue
-- codes (missing_name, missing_contact, stale, possible_duplicate, …). Cached so
-- a commander dashboard over 10k records does not recompute on every request;
-- refreshed by modules.quality.recalculate_all (CLI / nightly job).
CREATE TABLE IF NOT EXISTS data_quality_scores (
    person_id TEXT PRIMARY KEY,
    score INTEGER,  -- 0-100
    completeness INTEGER,
    confidence INTEGER,
    freshness INTEGER,
    issues TEXT,  -- JSON array of issue codes
    calculated_at TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quality_score ON data_quality_scores(score);

-- Scheduled SITREP reports (plan-13 §4). An operator registers a recurring
-- report (format + recipients + cron-ish schedule); the runner (CLI / cron)
-- generates the SITREP and delivers it via email/webhook, stamping last_run_at.
-- Schedule is a coarse interval keyword ('hourly','daily','weekly') or a raw cron
-- string; the runner only needs "is it due?" so we keep it simple and tolerant.
CREATE TABLE IF NOT EXISTS scheduled_reports (
    id TEXT PRIMARY KEY,
    operation_id TEXT,
    name TEXT,
    format TEXT CHECK(format IN ('pdf','html','json')),
    schedule_cron TEXT,
    recipients TEXT,  -- comma-separated emails or webhook ids
    last_run_at TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scheduled_reports_active ON scheduled_reports(active);

-- Migration tracking (plan-15 §11). The hand-rolled migration runner
-- (``migrate.py``) records each applied migration here so ``egi migrate`` is
-- idempotent and ``egi migrate --check`` can fail CI when migrations are pending.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- System events for operators (plan-15 §11) — distinct from the audit log, which
-- is about *who did what*. This is about *what the system did*: startup, backup
-- success/failure, migration applied, degraded health. Server-local, never synced.
CREATE TABLE IF NOT EXISTS system_events (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL CHECK(level IN ('info','warning','error')),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,  -- JSON
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_system_events_level ON system_events(level, created_at);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type, created_at);

-- Shelter & refugee information hub (plan-20). Shelters were previously a
-- frontend-only demo list; this promotes them to first-class, server-backed
-- records so capacity, services, contact info, an official update feed, and
-- check-ins can be shared across devices and synced offline-first. All tables
-- are additive and loosely coupled to the rest of the schema by id references.
--
-- `services`, `supply_needs`, and `target_populations` are JSON arrays (TEXT).
-- `accepting_new` is the simple "is there room?" flag responders/victims need.
-- `trust` mirrors the moderation trust model: official (verified staff) >
-- volunteer > crowd; lower-trust shelters are visually flagged in the UI.
CREATE TABLE IF NOT EXISTS shelters (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    name TEXT,
    kind TEXT,                       -- 'refugio' | 'hospital'
    address TEXT,
    lat REAL,
    lon REAL,
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    hours TEXT,
    capacity_total INTEGER,
    capacity_available INTEGER,
    beds_available INTEGER,
    occupancy INTEGER,
    accepting_new INTEGER DEFAULT 1,
    services TEXT,                    -- JSON array of service codes
    supply_needs TEXT,               -- JSON array of needed-item codes
    target_populations TEXT,         -- JSON array of population codes
    notes TEXT,
    source TEXT DEFAULT 'web',
    trust TEXT DEFAULT 'crowd',      -- 'official' | 'volunteer' | 'crowd'
    operator_user_id TEXT,           -- user who claimed/verified this shelter
    last_update_at TEXT,
    last_update_source TEXT,         -- 'official' | 'volunteer' | 'crowd'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shelters_disaster ON shelters(disaster_id);
CREATE INDEX IF NOT EXISTS idx_shelters_updated_at ON shelters(updated_at);

-- Official feed / updates from shelter operators (plan-20 §6). Append-only
-- timeline per shelter. `author_role` records who posted (official=verified
-- staff, volunteer, system); `services_changed`/`occupancy_delta` let an update
-- also carry a structured change the client can apply. `expires_at` lets a
-- transient notice (e.g. "full for the next hour") fall out of the feed.
CREATE TABLE IF NOT EXISTS shelter_updates (
    id TEXT PRIMARY KEY,
    shelter_id TEXT NOT NULL,
    disaster_id TEXT,
    author_id TEXT,
    author_name TEXT,
    author_role TEXT,                -- 'official' | 'volunteer' | 'system'
    message TEXT,
    services_changed TEXT,           -- JSON
    occupancy_delta INTEGER,
    source TEXT DEFAULT 'web',       -- 'web' | 'android' | 'sms' | 'mesh'
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_shelter_updates_shelter ON shelter_updates(shelter_id, created_at);

-- "I am at a shelter" self-reporting (plan-20 §8). A lightweight check-in tying
-- a person's alias to a shelter so family searching by alias can see "last seen
-- at <shelter>". `person_id` is optional (links to a registry person record when
-- one exists). Synced offline-first like person records.
CREATE TABLE IF NOT EXISTS shelter_checkins (
    id TEXT PRIMARY KEY,
    shelter_id TEXT NOT NULL,
    disaster_id TEXT,
    alias TEXT,
    person_id TEXT,
    note TEXT,
    source TEXT DEFAULT 'web',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shelter_checkins_shelter ON shelter_checkins(shelter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_shelter_checkins_alias ON shelter_checkins(alias);

-- One-time shelter-claim tokens (plan-20 §9). A commander issues a token for a
-- shelter; a shelter operator redeems it to become the verified operator of that
-- shelter. Stored only as SHA-256(token) like user_tokens — the raw token is
-- shown once at issuance. `revoked=1` disables it without losing the audit trail.
CREATE TABLE IF NOT EXISTS shelter_tokens (
    token_hash TEXT PRIMARY KEY,
    shelter_id TEXT NOT NULL,
    label TEXT,
    issued_by TEXT,
    claimed_by_user_id TEXT,
    claimed_at TEXT,
    revoked INTEGER DEFAULT 0,
    expires_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shelter_tokens_shelter ON shelter_tokens(shelter_id);

-- Offline routing packs (plan-21, Phase 2). A routing pack is a small cached
-- road-network graph (nodes + bidirectional edges with precomputed metres) that
-- the PWA downloads once and runs an on-device A* over, so offline routes follow
-- actual roads instead of a straight line. Server-local + additive: the server
-- only stores/serves the JSON graph file; all pathfinding compute is client-side.
-- The graph lives in a JSON file under `data/routing_packs/`; this table is just
-- the metadata index (region, bbox, counts, size, version, path). `bbox` is a
-- JSON `[minLon, minLat, maxLon, maxLat]` TEXT. Upserts are timestamp/version
-- guarded like /sync so a stale pack can't clobber a newer one.
CREATE TABLE IF NOT EXISTS routing_packs (
    id TEXT PRIMARY KEY,
    region TEXT,
    bbox TEXT,                       -- JSON [minLon, minLat, maxLon, maxLat]
    node_count INTEGER,
    edge_count INTEGER,
    size_bytes INTEGER,
    version INTEGER,
    file_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_routing_packs_region ON routing_packs(region);

-- Hazard zones (plan-21 Phase 4). A flagged danger area the map renders and the
-- offline router can avoid. `geometry` is a JSON dict — either a polygon
-- ({"kind":"polygon","coords":[[lat,lon],...]}) or a circle
-- ({"kind":"circle","center":[lat,lon],"radius_m":N}); `bbox` is a JSON
-- [minLon, minLat, maxLon, maxLat] computed server-side for cheap overlap
-- filtering. `source`/`reviewed` mirror the moderation trust model: official /
-- operator submissions land trusted (reviewed=1), community `hazard_report`s land
-- pending (reviewed=0) and await moderation; reviewed=-1 is a soft-delete.
-- Server-local + additive; loosely coupled by id references.
CREATE TABLE IF NOT EXISTS hazard_zones (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    type TEXT CHECK(type IN ('flood','landslide','fire','blocked_road','unsafe_zone')),
    geometry TEXT,                   -- JSON polygon|circle geometry
    bbox TEXT,                       -- JSON [minLon, minLat, maxLon, maxLat]
    active_from TEXT,
    active_until TEXT,
    source TEXT DEFAULT 'web',       -- 'web' | 'hazard_report' | 'official'
    confidence TEXT,                 -- 'low' | 'medium' | 'high'
    reviewed INTEGER DEFAULT 0,      -- 0 pending, 1 approved, -1 rejected
    reporter_name TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hazards_disaster ON hazard_zones(disaster_id);
CREATE INDEX IF NOT EXISTS idx_hazards_reviewed ON hazard_zones(reviewed);

-- Shareable route records (plan-21 Phase 5). A route share is a victim/responder
-- broadcasting "here is a usable path from A to B" so others can reuse it (e.g. a
-- safe walking route around flooding). `polyline` is a JSON [[lat,lon],...] TEXT
-- decoded on read; `mode` is walk|drive; `source` records the channel
-- (web|android|mesh). `dedup_key` is a server-computed hash of the rounded
-- origin/dest + author + mode used to collapse near-identical re-shares within a
-- short window (plan-21 §8.4) instead of inserting duplicates. Upserts are
-- timestamp-guarded last-write-wins on id like /sync. Server-local + additive.
CREATE TABLE IF NOT EXISTS route_shares (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    origin_lat REAL,
    origin_lon REAL,
    dest_lat REAL,
    dest_lon REAL,
    dest_name TEXT,
    polyline TEXT,                   -- JSON [[lat,lon], ...]
    mode TEXT DEFAULT 'walk',        -- 'walk' | 'drive'
    author_alias TEXT,
    note TEXT,
    dedup_key TEXT,
    source TEXT DEFAULT 'web',       -- 'web' | 'android' | 'mesh'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_route_shares_disaster ON route_shares(disaster_id);
CREATE INDEX IF NOT EXISTS idx_route_shares_dedup ON route_shares(dedup_key);

-- Evacuation corridors (plan-21 Phase 6). An official recommended path out of a
-- danger area, rendered on the map. `path` is a JSON [[lat,lon],...] TEXT decoded
-- on read; `bbox` is a server-computed JSON [minLon, minLat, maxLon, maxLat] for
-- cheap overlap filtering. `status` is open|congested|closed and `mode` is
-- drive|walk|transit. Writes are operator-gated and land trusted (source
-- 'official'); upserts are timestamp-guarded last-write-wins on id like /sync.
-- Server-local + additive.
CREATE TABLE IF NOT EXISTS evacuation_corridors (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    name TEXT,
    status TEXT DEFAULT 'open' CHECK(status IN ('open','congested','closed')),
    mode TEXT DEFAULT 'drive',       -- 'drive' | 'walk' | 'transit'
    path TEXT,                       -- JSON [[lat,lon], ...]
    bbox TEXT,                       -- JSON [minLon, minLat, maxLon, maxLat]
    note TEXT,
    source TEXT DEFAULT 'official',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_corridors_disaster ON evacuation_corridors(disaster_id);

-- User preferences, subscriptions & alerts (plan-24). A unified layer that lets
-- each user control what they SEE, what NOTIFIES them, and what they RELAY over
-- the mesh, per content category (people, animals, shelters, hazards, …). All
-- tables are additive, server-local, and keyed by `user_id` (a real account id,
-- or a guest/device alias for anonymous users). Defaults live in
-- modules/preferences.py, so an absent row means "use the default" — we only
-- persist rows the user has actually changed. Upserts are timestamp-guarded
-- last-write-wins on `updated_at` like /sync, so a stale device can't clobber a
-- newer change synced from another device.
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    display_enabled INTEGER DEFAULT 1,
    notify_enabled INTEGER DEFAULT 1,
    mesh_relay_enabled INTEGER DEFAULT 1,
    radius_meters INTEGER,             -- per-category "near me" override (NULL = use global)
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, category)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);

-- Per-user global settings that are not category-specific: the global "near me"
-- radius, an optional home anchor for radius filtering, a quiet-hours window, and
-- a batch-notifications flag (diaspora moderators get digests, not a flood). One
-- row per user; absent = all defaults.
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    radius_meters INTEGER,             -- global "near me" radius in metres (NULL/0 = off)
    home_lat REAL,
    home_lon REAL,
    quiet_hours_start INTEGER,         -- hour 0-23 (NULL = no quiet hours)
    quiet_hours_end INTEGER,           -- hour 0-23
    batch_notifications INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Operation/disaster subscriptions (plan-24 Phase 6). A user can subscribe to a
-- specific operation to scope updates, and `muted` lets them stay enrolled while
-- silencing notifications without leaving. Auto-subscription happens when a user
-- creates a report or joins an SAR operation. Keyed (user_id, operation_id).
CREATE TABLE IF NOT EXISTS operation_subscriptions (
    user_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    muted INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, operation_id)
);

CREATE INDEX IF NOT EXISTS idx_operation_subscriptions_op ON operation_subscriptions(operation_id);
"""

# Default action-plan task seed list (plan-09 §6). Inserted into task_templates
# on first init only; deployments may edit the table afterwards.
DEFAULT_TASK_TEMPLATES = [
    "Recolectar documentos de identidad y fotos.",
    "Contactar hospitales y servicios de emergencia.",
    "Rastrear última posición del teléfono / IMEI.",
    "Revisar transacciones bancarias y registros de transporte público.",
    "Entrevistar testigos y familiares.",
    "Coordinar grupos de búsqueda y asignar sectores.",
]

# Operational columns added to the existing `events` table (plan-09 §4). Added by
# the idempotent migration so pre-existing PFIF event rows gain them. NOTE:
# `status` is NOT here — the column already exists (PFIF). Its operational value
# set ('open','paused','closed') is enforced at the app layer (models.py
# VALID_OPERATION_STATUSES) rather than a SQLite CHECK, because SQLite cannot add
# a CHECK constraint to an existing column without a full table rebuild.
EVENTS_NEW_COLUMNS = {
    "commander_id": "TEXT",
    "is_practice": "INTEGER DEFAULT 0",
    "started_at": "TEXT",
    "closed_at": "TEXT",
    "closed_reason": "TEXT",
    "utm_x": "REAL",
    "utm_y": "REAL",
    "municipality": "TEXT",
    "contact_person": "TEXT",
    "contact_phone": "TEXT",
}

# New PFIF columns added to the existing `persons` table. Used by the migration
# helper so pre-existing databases gain them without a destructive rebuild.
PERSONS_NEW_COLUMNS = {
    "given_name": "TEXT",
    "family_name": "TEXT",
    "cedula": "TEXT",
    "sex": "TEXT",
    "photo_url": "TEXT",
    "last_known_location": "TEXT",
    "import_batch_id": "TEXT",
    # Mesh provenance: who first created the record and how many hops it travelled.
    "origin_device": "TEXT",
    "hop_count": "INTEGER DEFAULT 0",
    # Fuzzy-dedup: when a person is merged into a canonical record, this holds the
    # canonical id. Non-null rows are soft-deleted duplicates (never hard-deleted),
    # hidden from search but kept for provenance/history.
    "merged_into": "TEXT",
    # Data retention (plan-07 §11): ISO-8601 instant after which the record is
    # eligible for operator retention review / anonymization. Server-local
    # (not synced); preserved across sync upserts like merged_into.
    "retained_until": "TEXT",
    # Geospatial last-seen coordinates (plan-10). Synced like other person fields.
    "lat": "REAL",
    "lon": "REAL",
}

# New columns added to the existing `reports` table (same idempotent migration).
REPORTS_NEW_COLUMNS = {
    # Confidence tier of the observation: self|official|witness|ocr. Drives the
    # person's derived status (see modules/confidence.py).
    "confidence": "TEXT",
    # Geospatial coordinates of the observation (plan-10).
    "lat": "REAL",
    "lon": "REAL",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)
        _migrate_persons_columns(db)
        _migrate_table_columns(db, "reports", REPORTS_NEW_COLUMNS)
        _migrate_table_columns(db, "events", EVENTS_NEW_COLUMNS)
        # `deleted` was added to action_plans after its first release; migrate old DBs.
        _migrate_table_columns(db, "action_plans", {"deleted": "INTEGER DEFAULT 0"})
        # `notes` was added to action_plan_tasks after first release; migrate old DBs.
        _migrate_table_columns(db, "action_plan_tasks", {"notes": "TEXT"})
        # cedula index is created AFTER the migration so it works on old DBs that
        # gain the `cedula` column only during migration.
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_cedula ON persons(cedula)"
        )
        # lat/lon indexes are created AFTER migration so they work on old DBs that
        # gain the lat/lon columns only during the migration above (plan-10).
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_lat_lon ON persons(lat, lon)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_lat_lon ON reports(lat, lon)"
        )
        _seed_task_templates(db)
        # Apply any pending versioned migrations (plan-15 §7.2). Hand-rolled,
        # idempotent runner; no-op on a fresh DB whose SCHEMA already matches.
        try:
            import migrate

            migrate.apply_pending(db)
        except Exception as exc:  # never block startup on a migration error
            print(f"[EGI] migration runner skipped: {exc}")
        db.commit()
    # Seed the offline-routing demo pack (plan-21 Phase 2) AFTER the init
    # transaction commits, so the pack module opens its own clean connection
    # rather than contending with this one. Idempotent + version-guarded inside
    # the module; best-effort so a write failure never blocks startup.
    try:
        import modules.routing as routing

        routing.seed_demo_packs()
    except Exception as exc:
        print(f"[EGI] routing demo-pack seed skipped: {exc}")
    # Seed the demo evacuation corridor (plan-21 Phase 6) the same way: after the
    # init transaction commits, idempotent inside the module, best-effort.
    try:
        import modules.corridors as corridors

        corridors.seed_demo_corridor()
    except Exception as exc:
        print(f"[EGI] evacuation-corridor seed skipped: {exc}")


def _seed_task_templates(db: sqlite3.Connection) -> None:
    """Seed the default action-plan task templates if the table is empty.

    Idempotent: only inserts when no templates exist, so a deployment that
    edits/removes templates keeps its customizations across restarts.
    """
    count = db.execute("SELECT COUNT(*) FROM task_templates").fetchone()[0]
    if count:
        return
    now = now_iso()
    for i, title in enumerate(DEFAULT_TASK_TEMPLATES):
        db.execute(
            "INSERT INTO task_templates (id, title, description, sort_order, active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (f"tmpl-{i+1:02d}", title, None, i, now),
        )


def _migrate_persons_columns(db: sqlite3.Connection) -> None:
    """Add any missing PFIF columns to an existing `persons` table."""
    _migrate_table_columns(db, "persons", PERSONS_NEW_COLUMNS)


def _migrate_table_columns(db: sqlite3.Connection, table: str, columns: dict) -> None:
    """Add any missing columns to an existing table.

    Idempotent: reads PRAGMA table_info and only ALTERs columns that are absent,
    so it is safe to run on every startup and repeatedly.
    """
    existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    for col, coltype in columns.items():
        if col not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


if __name__ == "__main__":
    # `python -m db` initializes ./data/egi.db (idempotent). Documented in CLAUDE.md.
    init_db()
    print(f"Initialized {DB_PATH}")
