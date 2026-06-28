-- 0011_volunteer_profiles — plan-27.5 Phase 1 (volunteer registry).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates this
-- table, so on a fresh DB this is a no-op marker. On an older DB it adds the
-- additive, server-local volunteer registry. A profile is optional — anonymous
-- volunteers still join operations via sar_volunteers without one. Upserts are
-- timestamp-guarded last-write-wins on id (handled in modules/volunteers.py)
-- like /sync, so offline/mesh copies merge cleanly.

CREATE TABLE IF NOT EXISTS volunteer_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    device_id TEXT,
    display_name TEXT,
    contact TEXT,
    region TEXT,
    lat REAL,
    lon REAL,
    languages TEXT,
    skills TEXT,
    availability TEXT DEFAULT 'available',
    mobility TEXT DEFAULT 'local',
    visible INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_volunteer_profiles_user ON volunteer_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_volunteer_profiles_device ON volunteer_profiles(device_id);
CREATE INDEX IF NOT EXISTS idx_volunteer_profiles_availability ON volunteer_profiles(availability);
CREATE INDEX IF NOT EXISTS idx_volunteer_profiles_updated_at ON volunteer_profiles(updated_at);
