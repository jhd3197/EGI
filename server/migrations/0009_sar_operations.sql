-- 0009_sar_operations — plan-26 (Search & Rescue operations workflow).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates these
-- tables, so on a fresh DB this is a no-op marker. On an older DB it adds the
-- additive, server-local SAR tables. Namespaced `sar_*` so they never collide
-- with the plan-09 `operations`/`events` surface. All statements are IF NOT
-- EXISTS so re-running is safe. Upserts are timestamp-guarded last-write-wins on
-- id (handled in modules/sar.py) like /sync.

CREATE TABLE IF NOT EXISTS sar_operations (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    name TEXT,
    description TEXT,
    status TEXT DEFAULT 'active',
    zone_lat REAL,
    zone_lon REAL,
    zone_radius_m INTEGER,
    created_by TEXT,
    created_by_user_id TEXT,
    closed_at TEXT,
    closed_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sar_operations_disaster ON sar_operations(disaster_id);
CREATE INDEX IF NOT EXISTS idx_sar_operations_status ON sar_operations(status);
CREATE INDEX IF NOT EXISTS idx_sar_operations_updated_at ON sar_operations(updated_at);

CREATE TABLE IF NOT EXISTS sar_operation_persons (
    operation_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (operation_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_sar_operation_persons_person ON sar_operation_persons(person_id);

CREATE TABLE IF NOT EXISTS sar_sectors (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    name TEXT,
    status TEXT DEFAULT 'unassigned',
    lat REAL,
    lon REAL,
    radius_m INTEGER,
    bbox TEXT,
    assigned_to TEXT,
    assigned_user_id TEXT,
    assigned_volunteer_id TEXT,
    notes TEXT,
    cleared_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sar_sectors_operation ON sar_sectors(operation_id);

CREATE TABLE IF NOT EXISTS sar_tasks (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    sector_id TEXT,
    title TEXT,
    kind TEXT,
    done INTEGER DEFAULT 0,
    notes TEXT,
    completed_by TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sar_tasks_operation ON sar_tasks(operation_id);
CREATE INDEX IF NOT EXISTS idx_sar_tasks_sector ON sar_tasks(sector_id);

CREATE TABLE IF NOT EXISTS sar_volunteers (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    sector_id TEXT,
    alias TEXT,
    user_id TEXT,
    device_id TEXT,
    status TEXT DEFAULT 'joined',
    checked_in_at TEXT,
    checked_out_at TEXT,
    last_seen_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sar_volunteers_operation ON sar_volunteers(operation_id);
CREATE INDEX IF NOT EXISTS idx_sar_volunteers_sector ON sar_volunteers(sector_id);

CREATE TABLE IF NOT EXISTS sar_field_reports (
    id TEXT PRIMARY KEY,
    operation_id TEXT,
    sector_id TEXT,
    person_id TEXT,
    type TEXT,
    note TEXT,
    lat REAL,
    lon REAL,
    photo_url TEXT,
    reporter_alias TEXT,
    reporter_user_id TEXT,
    origin_device TEXT,
    reviewed INTEGER DEFAULT 0,
    confirmed_by TEXT,
    applied INTEGER DEFAULT 0,
    source TEXT DEFAULT 'web',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sar_field_reports_operation ON sar_field_reports(operation_id);
CREATE INDEX IF NOT EXISTS idx_sar_field_reports_updated_at ON sar_field_reports(updated_at);
