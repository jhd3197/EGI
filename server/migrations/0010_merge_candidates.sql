-- 0010_merge_candidates — plan-27 (Data quality & deduplication engine).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates this
-- table, so on a fresh DB this is a no-op marker. On an older DB it adds the
-- additive, server-local `merge_candidates` table that persists scored
-- probable-duplicate person pairs for human review (plan-27 Phase 2). The actual
-- merge still flows through modules/duplicates.merge_cluster so provenance,
-- history and webhooks are preserved; this table only records the scored pair and
-- the reviewer's decision. Server-local, never synced over the mesh.

CREATE TABLE IF NOT EXISTS merge_candidates (
    id TEXT PRIMARY KEY,
    person_a_id TEXT NOT NULL,
    person_b_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    tier TEXT,
    reasons TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','merged','not_match','needs_info')),
    reviewed_by TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_merge_candidates_status ON merge_candidates(status);
CREATE INDEX IF NOT EXISTS idx_merge_candidates_pair
    ON merge_candidates(person_a_id, person_b_id);
