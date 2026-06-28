-- Plan 24.5: Raw-source provenance.
--
-- The persons.reports import_batch_id columns are added idempotently by
-- db.py's PERSONS_NEW_COLUMNS / REPORTS_NEW_COLUMNS helpers, so this migration
-- only creates the import_batches table and indexes for databases that existed
-- before that table was added to db.SCHEMA. All statements are IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    disaster_id TEXT,
    source_type TEXT NOT NULL,
    original_filename TEXT,
    stored_filename TEXT,
    file_hash TEXT,
    file_size INTEGER,
    media_type TEXT,
    extraction_method TEXT,
    record_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','processed','partial','failed')),
    error_log TEXT,
    uploaded_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_import_batches_disaster ON import_batches(disaster_id);
CREATE INDEX IF NOT EXISTS idx_import_batches_hash ON import_batches(file_hash);
CREATE INDEX IF NOT EXISTS idx_import_batches_source_type ON import_batches(source_type);
