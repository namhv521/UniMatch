-- Additive portal schema. PostgreSQL connection uses unimatch_portal search_path.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL, name TEXT NOT NULL,
    UNIQUE(provider, subject)
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS email_accounts (
    email TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
    password_hash TEXT NOT NULL, activation_hash TEXT,
    role TEXT NOT NULL CHECK (role IN ('student','faculty','dean')),
    advisor_id TEXT, advisor_semester TEXT
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
CREATE TABLE IF NOT EXISTS thesis_semesters (
    semester TEXT PRIMARY KEY, threshold INTEGER NOT NULL DEFAULT 70,
    revision INTEGER NOT NULL DEFAULT 0, proposal TEXT, published TEXT
);
CREATE TABLE IF NOT EXISTS thesis_students (
    semester TEXT NOT NULL REFERENCES thesis_semesters(semester),
    user_id TEXT NOT NULL REFERENCES users(id), profile TEXT NOT NULL,
    PRIMARY KEY (semester, user_id)
);
CREATE TABLE IF NOT EXISTS thesis_requests (
    semester TEXT NOT NULL, user_id TEXT NOT NULL, advisor_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected','withdrawn')),
    PRIMARY KEY (semester, user_id, advisor_id),
    FOREIGN KEY (semester, user_id) REFERENCES thesis_students(semester, user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS thesis_one_active_request
    ON thesis_requests(semester, user_id) WHERE status IN ('pending','accepted');
