CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_hash char(64) PRIMARY KEY,
    dataset_hash char(64) NOT NULL,
    feature_hash char(64) NOT NULL,
    split_hash char(64) NOT NULL,
    student_order_hash char(64) NOT NULL,
    advisor_order_hash char(64) NOT NULL,
    provenance jsonb NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'),
    CHECK (dataset_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS snapshots_dataset_hash ON snapshots(dataset_hash);

CREATE TABLE IF NOT EXISTS students (
    snapshot_hash char(64) NOT NULL REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    student_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    profile jsonb NOT NULL,
    PRIMARY KEY (snapshot_hash, student_id),
    UNIQUE (snapshot_hash, ordinal)
);

CREATE TABLE IF NOT EXISTS advisors (
    snapshot_hash char(64) NOT NULL REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    advisor_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    profile jsonb NOT NULL,
    PRIMARY KEY (snapshot_hash, advisor_id),
    UNIQUE (snapshot_hash, ordinal)
);

CREATE TABLE IF NOT EXISTS split_memberships (
    snapshot_hash char(64) NOT NULL,
    student_id text NOT NULL,
    split_name text NOT NULL CHECK (split_name IN ('train', 'validation', 'test', 'future')),
    position integer NOT NULL CHECK (position >= 0),
    PRIMARY KEY (snapshot_hash, student_id),
    UNIQUE (snapshot_hash, split_name, position),
    FOREIGN KEY (snapshot_hash, student_id)
        REFERENCES students(snapshot_hash, student_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS split_memberships_lookup
    ON split_memberships(snapshot_hash, split_name, position);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id uuid PRIMARY KEY,
    snapshot_hash char(64) NOT NULL REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    endpoint text NOT NULL CHECK (endpoint IN ('simulate', 'allocate')),
    mode text NOT NULL CHECK (mode IN ('semantic', 'non_rl', 'rl', 'rl_research')),
    algorithm text NOT NULL,
    dataset text NOT NULL,
    seed integer NOT NULL CHECK (seed >= 0),
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS simulation_runs_snapshot_created
    ON simulation_runs(snapshot_hash, created_at DESC);

CREATE TABLE IF NOT EXISTS feedback (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_hash char(64) REFERENCES snapshots(snapshot_hash) ON DELETE RESTRICT,
    mode text NOT NULL CHECK (mode IN ('semantic', 'non_rl', 'rl', 'rl_research')),
    algorithm text NOT NULL,
    helpful boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS feedback_snapshot_created
    ON feedback(snapshot_hash, created_at DESC);
