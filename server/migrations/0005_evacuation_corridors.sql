-- 0005_evacuation_corridors — plan-21 Phase 6 (evacuation-corridor data).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates this
-- table, so on a fresh DB this is a no-op marker. On an older DB that predates
-- evacuation corridors it adds the table + index. An evacuation corridor is an
-- official recommended path out of a danger area — `path` is a JSON [[lat,lon],...]
-- TEXT (decoded on read), `bbox` is a server-computed JSON [minLon,minLat,maxLon,
-- maxLat] for cheap overlap filtering; `status` is open|congested|closed and
-- `mode` is drive|walk|transit. Upserts are timestamp-guarded last-write-wins on
-- id like /sync.

CREATE TABLE IF NOT EXISTS evacuation_corridors (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    name TEXT,
    status TEXT DEFAULT 'open' CHECK(status IN ('open','congested','closed')),
    mode TEXT DEFAULT 'drive',       -- 'drive' | 'walk' | 'transit'
    path TEXT,                       -- JSON [[lat,lon], ...]
    bbox TEXT,                       -- JSON [minLon, minLat, maxLon, maxLat]
    note TEXT,
    source TEXT DEFAULT 'official',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_corridors_disaster ON evacuation_corridors(disaster_id);
