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
"""

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
}

# New columns added to the existing `reports` table (same idempotent migration).
REPORTS_NEW_COLUMNS = {
    # Confidence tier of the observation: self|official|witness|ocr. Drives the
    # person's derived status (see modules/confidence.py).
    "confidence": "TEXT",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)
        _migrate_persons_columns(db)
        _migrate_table_columns(db, "reports", REPORTS_NEW_COLUMNS)
        # cedula index is created AFTER the migration so it works on old DBs that
        # gain the `cedula` column only during migration.
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_cedula ON persons(cedula)"
        )
        db.commit()


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
