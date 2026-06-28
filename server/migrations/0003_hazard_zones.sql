-- 0003_hazard_zones — plan-21 Phase 4 (hazard-zone data model).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates this
-- table, so on a fresh DB this is a no-op marker. On an older DB that predates
-- hazard zones it adds the table + indexes. `geometry` is a JSON polygon|circle
-- dict; `bbox` is a JSON [minLon, minLat, maxLon, maxLat] computed server-side.
-- `source`/`reviewed` mirror the moderation trust model (community hazard_report
-- rows land reviewed=0; official/operator rows land reviewed=1; -1 is soft-delete).

CREATE TABLE IF NOT EXISTS hazard_zones (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    type TEXT CHECK(type IN ('flood','landslide','fire','blocked_road','unsafe_zone')),
    geometry TEXT,
    bbox TEXT,
    active_from TEXT,
    active_until TEXT,
    source TEXT DEFAULT 'web',
    confidence TEXT,
    reviewed INTEGER DEFAULT 0,
    reporter_name TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hazards_disaster ON hazard_zones(disaster_id);
CREATE INDEX IF NOT EXISTS idx_hazards_reviewed ON hazard_zones(reviewed);
