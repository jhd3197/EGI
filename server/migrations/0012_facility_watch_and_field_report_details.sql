-- 0012_facility_watch_and_field_report_details — plan-27.5 Phases 3/4/5.
--
-- Idempotent: the live schema in db.SCHEMA already creates the table below, so on
-- a fresh DB this is a no-op marker. The additive columns on existing tables
-- (sar_volunteers.role, sar_field_reports.checklist/facility_id) are handled by
-- db._migrate_table_columns at init (PRAGMA-guarded ALTERs), which is the
-- established pattern for column adds — SQLite cannot ADD COLUMN IF NOT EXISTS,
-- so they are intentionally NOT repeated here. This migration only records the
-- new facility-watch table for older DBs and version parity.

CREATE TABLE IF NOT EXISTS sar_facility_watch (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (operation_id, facility_id)
);

CREATE INDEX IF NOT EXISTS idx_sar_facility_watch_operation ON sar_facility_watch(operation_id);
CREATE INDEX IF NOT EXISTS idx_sar_facility_watch_facility ON sar_facility_watch(facility_id);
