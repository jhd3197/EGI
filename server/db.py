import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = Path(os.environ.get("DB_PATH", "./data/egi.db")).resolve()

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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_persons_disaster ON persons(disaster_id);
CREATE INDEX IF NOT EXISTS idx_persons_status ON persons(status);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_location ON persons(location);
CREATE INDEX IF NOT EXISTS idx_persons_updated_at ON persons(updated_at);
CREATE INDEX IF NOT EXISTS idx_persons_source ON persons(source);

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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_person ON reports(person_id);

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
        db.commit()


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
