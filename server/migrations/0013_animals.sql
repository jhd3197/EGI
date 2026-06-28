-- 0013_animals — plan-28 Missing Animals (Pets).
--
-- Idempotent: the live schema in db.SCHEMA already creates the `animals` table on
-- a fresh DB, so there this is a no-op marker. For an existing pre-28 DB this
-- creates the new, additive `animals` table (a PARALLEL track to persons — never
-- mixed with the person registry) plus its indexes. Animals ride the same /sync
-- last-write-wins path as persons but are always tagged record_type='animal'.

CREATE TABLE IF NOT EXISTS animals (
    id TEXT PRIMARY KEY,
    record_type TEXT DEFAULT 'animal',
    disaster_id TEXT,
    status TEXT CHECK(status IN ('missing','seen','found','reunited','deceased','unknown')),
    species TEXT,
    breed TEXT,
    name TEXT,
    sex TEXT,
    size TEXT,
    color TEXT,
    distinguishing_marks TEXT,
    microchip TEXT,
    photo_url TEXT,
    photos TEXT,
    last_seen_location TEXT,
    last_seen_at TEXT,
    lat REAL,
    lon REAL,
    owner_name TEXT,
    owner_contact TEXT,
    reporter_id TEXT,
    reporter_name TEXT,
    notes TEXT,
    source TEXT DEFAULT 'web',
    reviewed INTEGER DEFAULT 0,
    origin_device TEXT,
    hop_count INTEGER DEFAULT 0,
    merged_into TEXT,
    shelter_id TEXT,
    intake_at TEXT,
    condition_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_animals_disaster ON animals(disaster_id);
CREATE INDEX IF NOT EXISTS idx_animals_status ON animals(status);
CREATE INDEX IF NOT EXISTS idx_animals_species ON animals(species);
CREATE INDEX IF NOT EXISTS idx_animals_location ON animals(last_seen_location);
CREATE INDEX IF NOT EXISTS idx_animals_reporter ON animals(reporter_id);
CREATE INDEX IF NOT EXISTS idx_animals_microchip ON animals(microchip);
CREATE INDEX IF NOT EXISTS idx_animals_shelter ON animals(shelter_id);
CREATE INDEX IF NOT EXISTS idx_animals_updated_at ON animals(updated_at);
CREATE INDEX IF NOT EXISTS idx_animals_lat_lon ON animals(lat, lon);
