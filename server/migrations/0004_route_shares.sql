-- 0004_route_shares — plan-21 Phase 5 (shareable route records).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates this
-- table, so on a fresh DB this is a no-op marker. On an older DB that predates
-- route sharing it adds the table + indexes. A route share is a victim/responder
-- broadcasting "here is a usable path from A to B" — `polyline` is a JSON
-- [[lat,lon],...] TEXT (decoded on read); `mode` is walk|drive; `dedup_key` is a
-- server-computed hash (rounded origin/dest + author + mode) used to collapse
-- near-identical re-shares within a short window (plan-21 §8.4).

CREATE TABLE IF NOT EXISTS route_shares (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    origin_lat REAL,
    origin_lon REAL,
    dest_lat REAL,
    dest_lon REAL,
    dest_name TEXT,
    polyline TEXT,                   -- JSON [[lat,lon], ...]
    mode TEXT DEFAULT 'walk',        -- 'walk' | 'drive'
    author_alias TEXT,
    note TEXT,
    dedup_key TEXT,
    source TEXT DEFAULT 'web',       -- 'web' | 'android' | 'mesh'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_route_shares_disaster ON route_shares(disaster_id);
CREATE INDEX IF NOT EXISTS idx_route_shares_dedup ON route_shares(dedup_key);
