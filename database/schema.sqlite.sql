BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_hash TEXT PRIMARY KEY,
    dataset_hash TEXT NOT NULL,
    feature_hash TEXT NOT NULL,
    split_hash TEXT NOT NULL,
    student_order_hash TEXT NOT NULL,
    advisor_order_hash TEXT NOT NULL,
    provenance TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    snapshot_hash TEXT NOT NULL REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    student_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    profile TEXT NOT NULL,
    PRIMARY KEY (snapshot_hash, student_id),
    UNIQUE (snapshot_hash, ordinal)
);

CREATE TABLE IF NOT EXISTS advisors (
    snapshot_hash TEXT NOT NULL REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    advisor_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    profile TEXT NOT NULL,
    PRIMARY KEY (snapshot_hash, advisor_id),
    UNIQUE (snapshot_hash, ordinal)
);

CREATE TABLE IF NOT EXISTS split_memberships (
    snapshot_hash TEXT NOT NULL,
    student_id TEXT NOT NULL,
    split_name TEXT NOT NULL CHECK (split_name IN ('train', 'validation', 'test', 'future')),
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (snapshot_hash, student_id),
    UNIQUE (snapshot_hash, split_name, position),
    FOREIGN KEY (snapshot_hash, student_id)
        REFERENCES students(snapshot_hash, student_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS split_memberships_lookup
    ON split_memberships(snapshot_hash, split_name, position);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    snapshot_hash TEXT NOT NULL REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    endpoint TEXT NOT NULL CHECK (endpoint IN ('simulate', 'allocate')),
    mode TEXT NOT NULL CHECK (mode IN ('semantic', 'non_rl', 'rl', 'rl_research')),
    algorithm TEXT NOT NULL,
    dataset TEXT NOT NULL,
    seed INTEGER NOT NULL CHECK (seed >= 0),
    result TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS simulation_runs_snapshot_created
    ON simulation_runs(snapshot_hash, created_at DESC);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    created_at INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('semantic', 'non_rl', 'rl', 'rl_research')),
    algorithm TEXT NOT NULL,
    helpful INTEGER NOT NULL CHECK (helpful IN (0, 1)),
    snapshot_hash TEXT REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT
);

COMMIT;
