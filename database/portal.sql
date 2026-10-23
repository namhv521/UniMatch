-- Additive portal schema. PostgreSQL connection uses unimatch_portal search_path.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL, name TEXT NOT NULL,
    UNIQUE(provider, subject)
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
CREATE TABLE IF NOT EXISTS pending (
    state TEXT PRIMARY KEY, provider TEXT NOT NULL, verifier TEXT NOT NULL, expires DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    kind TEXT NOT NULL, record_key TEXT NOT NULL, scope_hash TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(kind, record_key)
);
CREATE INDEX IF NOT EXISTS records_owner ON records(scope_hash, kind);
CREATE TABLE IF NOT EXISTS catalogs (
    snapshot TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisors (
    snapshot TEXT NOT NULL REFERENCES catalogs(snapshot), advisor_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
    profile TEXT NOT NULL, PRIMARY KEY(snapshot, advisor_id)
);
CREATE TABLE IF NOT EXISTS model_bundles (
    bundle_key TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload BYTEA NOT NULL
);
