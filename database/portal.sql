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
CREATE TABLE IF NOT EXISTS email_password_resets (
    email TEXT PRIMARY KEY REFERENCES email_accounts(email), token_hash TEXT NOT NULL,
    expires DOUBLE PRECISION NOT NULL
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
    semester TEXT PRIMARY KEY, threshold INTEGER NOT NULL DEFAULT 15,
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
CREATE UNIQUE INDEX IF NOT EXISTS thesis_one_accepted_request
    ON thesis_requests(semester, user_id) WHERE status='accepted';
DROP INDEX IF EXISTS thesis_one_active_request;
CREATE TABLE IF NOT EXISTS thesis_preferences (
    semester TEXT NOT NULL, user_id TEXT NOT NULL,
    advisor_ids TEXT NOT NULL, topic_description TEXT NOT NULL,
    PRIMARY KEY (semester, user_id),
    FOREIGN KEY (semester, user_id) REFERENCES thesis_students(semester, user_id)
);
CREATE TABLE IF NOT EXISTS thesis_contacts (
    semester TEXT NOT NULL, user_id TEXT NOT NULL,
    email TEXT NOT NULL, phone TEXT NOT NULL,
    PRIMARY KEY (semester, user_id),
    FOREIGN KEY (semester, user_id) REFERENCES thesis_students(semester, user_id)
);
CREATE TABLE IF NOT EXISTS thesis_intake (
    semester TEXT PRIMARY KEY REFERENCES thesis_semesters(semester),
    roster TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS thesis_history (
    semester TEXT NOT NULL REFERENCES thesis_semesters(semester),
    revision INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('manual_save','publish','revoke')),
    actor_id TEXT NOT NULL REFERENCES users(id), actor_name TEXT NOT NULL,
    created_at TEXT NOT NULL, proposal_id TEXT NOT NULL, algorithm TEXT NOT NULL,
    reason TEXT NOT NULL, snapshot TEXT NOT NULL,
    PRIMARY KEY (semester, revision)
);
CREATE TABLE IF NOT EXISTS thesis_advisor_skills (
    advisor_id TEXT PRIMARY KEY,
    advisor_name TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT 'Khoa Công nghệ thông tin',
    academic_title TEXT NOT NULL DEFAULT '',
    research_domains TEXT NOT NULL DEFAULT '',
    topic_tags TEXT NOT NULL DEFAULT '',
    programming_languages TEXT NOT NULL DEFAULT '',
    frameworks_libraries TEXT NOT NULL DEFAULT '',
    databases TEXT NOT NULL DEFAULT '',
    ml_ai_methods TEXT NOT NULL DEFAULT '',
    software_engineering_methods TEXT NOT NULL DEFAULT '',
    research_methods TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    target_quota INTEGER,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS thesis_dossiers (
    semester TEXT NOT NULL,
    user_id TEXT NOT NULL,
    raw_title TEXT NOT NULL DEFAULT '',
    raw_description TEXT NOT NULL DEFAULT '',
    raw_background TEXT NOT NULL DEFAULT '',
    formal_title TEXT NOT NULL DEFAULT '',
    formal_summary TEXT NOT NULL DEFAULT '',
    methodology_scope TEXT NOT NULL DEFAULT '',
    normalized_skills TEXT NOT NULL DEFAULT '[]',
    taxonomy_tags TEXT NOT NULL DEFAULT '{}',
    normalizer_mode TEXT NOT NULL DEFAULT 'deterministic',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (semester, user_id),
    FOREIGN KEY (semester, user_id) REFERENCES thesis_students(semester, user_id)
);
CREATE TABLE IF NOT EXISTS thesis_milestones (
    semester TEXT NOT NULL,
    user_id TEXT NOT NULL,
    milestone_key TEXT NOT NULL CHECK (milestone_key IN ('proposal','midterm','final')),
    official_title TEXT NOT NULL DEFAULT '',
    submission_url TEXT NOT NULL DEFAULT '',
    submission_note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','submitted','revision_requested','approved')),
    advisor_feedback TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (semester, user_id, milestone_key),
    FOREIGN KEY (semester, user_id) REFERENCES thesis_students(semester, user_id)
);
CREATE TABLE IF NOT EXISTS thesis_outcomes (
    semester TEXT NOT NULL,
    user_id TEXT NOT NULL,
    advisor_id TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('excellent','satisfactory','needs_improvement')),
    skills_applied TEXT NOT NULL DEFAULT '',
    summary_note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (semester, user_id),
    FOREIGN KEY (semester, user_id) REFERENCES thesis_students(semester, user_id)
);
CREATE TABLE IF NOT EXISTS thesis_enrollments (
    semester TEXT NOT NULL REFERENCES thesis_semesters(semester),
    user_id TEXT NOT NULL REFERENCES users(id),
    student_id TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    PRIMARY KEY (semester, user_id)
);
