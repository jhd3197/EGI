-- 0001_baseline — plan-15 §11 schema additions (migration tracking + system events).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates these,
-- so on a fresh DB this is a no-op marker establishing the migration baseline.
-- On an older DB that predates the runner it adds the two tables. Future schema
-- changes should be added as new NNNN_*.sql files rather than editing db.SCHEMA.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_events (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL CHECK(level IN ('info','warning','error')),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_system_events_level ON system_events(level, created_at);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type, created_at);
