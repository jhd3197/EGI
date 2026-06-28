-- 0008_trust_safety_verification — plan-25 (Trust, Safety & Verification).
--
-- Idempotent (IF NOT EXISTS): the live schema in db.SCHEMA already creates these
-- tables, and the new persons.* trust columns are added idempotently by db.py's
-- PERSONS_NEW_COLUMNS helper. On a fresh DB this is a no-op marker; on an older
-- DB it adds the additive, server-local trust tables. All statements are
-- IF NOT EXISTS so re-running is safe.

CREATE TABLE IF NOT EXISTS device_reputation (
    device_id TEXT PRIMARY KEY,
    trust_tier TEXT DEFAULT 'low',
    reputation_score INTEGER DEFAULT 50,
    report_count INTEGER DEFAULT 0,
    flag_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    banned INTEGER DEFAULT 0,
    ban_reason TEXT,
    first_seen TEXT,
    last_seen TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_device_reputation_banned ON device_reputation(banned);

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT,
    description TEXT,
    public_key TEXT,
    verified INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS org_members (
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin','member')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    org_id TEXT,
    name TEXT NOT NULL,
    kind TEXT,
    address TEXT,
    lat REAL,
    lon REAL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_locations_org ON locations(org_id);

CREATE TABLE IF NOT EXISTS location_watchers (
    location_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    authorized_by TEXT,
    expires_at TEXT,
    revoked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (location_id, user_id)
);

CREATE TABLE IF NOT EXISTS trust_invites (
    token_hash TEXT PRIMARY KEY,
    target_type TEXT NOT NULL CHECK(target_type IN ('org','location')),
    target_id TEXT NOT NULL,
    grant_role TEXT,
    label TEXT,
    issued_by TEXT,
    claimed_by_user_id TEXT,
    claimed_at TEXT,
    revoked INTEGER DEFAULT 0,
    expires_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trust_invites_target ON trust_invites(target_type, target_id);

CREATE TABLE IF NOT EXISTS moderation_flags (
    id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    flag_reason TEXT,
    note TEXT,
    flagged_by TEXT,
    origin_device TEXT,
    severity TEXT DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    reviewed_by TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_moderation_flags_record ON moderation_flags(record_type, record_id);
CREATE INDEX IF NOT EXISTS idx_moderation_flags_status ON moderation_flags(status);

CREATE TABLE IF NOT EXISTS moderators (
    user_id TEXT PRIMARY KEY,
    display_name TEXT,
    languages TEXT,
    regions TEXT,
    trained INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
