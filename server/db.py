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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_persons_disaster ON persons(disaster_id);
CREATE INDEX IF NOT EXISTS idx_persons_status ON persons(status);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_location ON persons(location);
CREATE INDEX IF NOT EXISTS idx_persons_updated_at ON persons(updated_at);
CREATE INDEX IF NOT EXISTS idx_persons_source ON persons(source);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)


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
