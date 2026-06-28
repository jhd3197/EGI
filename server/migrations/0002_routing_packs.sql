-- 0002_routing_packs — plan-21 Phase 2 (offline routing packs).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates this
-- table, so on a fresh DB this is a no-op marker. On an older DB that predates
-- offline routing it adds the metadata index for cached road-network packs. The
-- graph JSON lives in a file under data/routing_packs/; this table only indexes
-- region/bbox/counts/version/path. bbox is a JSON [minLon, minLat, maxLon, maxLat].

CREATE TABLE IF NOT EXISTS routing_packs (
    id TEXT PRIMARY KEY,
    region TEXT,
    bbox TEXT,
    node_count INTEGER,
    edge_count INTEGER,
    size_bytes INTEGER,
    version INTEGER,
    file_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_routing_packs_region ON routing_packs(region);
