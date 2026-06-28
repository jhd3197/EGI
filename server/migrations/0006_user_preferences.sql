-- 0006_user_preferences — plan-24 Phase 1 (user preferences, settings & subscriptions).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates these
-- tables, so on a fresh DB this is a no-op marker. On an older DB that predates
-- the preference layer it adds the three additive, server-local tables.

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    display_enabled INTEGER DEFAULT 1,
    notify_enabled INTEGER DEFAULT 1,
    mesh_relay_enabled INTEGER DEFAULT 1,
    radius_meters INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, category)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    radius_meters INTEGER,
    home_lat REAL,
    home_lon REAL,
    quiet_hours_start INTEGER,
    quiet_hours_end INTEGER,
    batch_notifications INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operation_subscriptions (
    user_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    muted INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, operation_id)
);

CREATE INDEX IF NOT EXISTS idx_operation_subscriptions_op ON operation_subscriptions(operation_id);
