from __future__ import annotations

import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from backend.app.schemas import FeedbackRequest
from backend.app.storage import PostgresStorage, SQLiteFeedbackStore, snapshot_identity


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, query, params=None):
        self.calls.append((str(query), params))
        return self

    def cursor(self):
        return FakeCursor(self.calls)


class FakeCursor:
    def __init__(self, calls) -> None:
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def executemany(self, query, params) -> None:
        self.calls.append((str(query), list(params)))


def _service():
    return SimpleNamespace(
        provenance={
            "dataset_sha256": "d" * 64,
            "feature_sha256": "f" * 64,
            "split_sha256": "s" * 64,
            "student_order_sha256": "u" * 64,
            "advisor_order_sha256": "a" * 64,
        },
        theses=[
            {"student_id": "student-1", "thesis_title": "One"},
            {"student_id": "student-2", "thesis_title": "Two"},
        ],
        advisors=[{"advisor_id": "advisor-1", "advisor_name": "Advisor"}],
        split={
            "indices": {"train": [0], "validation": [1], "test": [], "future": []},
        },
    )


def test_snapshot_identity_includes_the_full_provenance_contract() -> None:
    """Catches rebuilt features being merged into an older dataset snapshot."""
    original = _service().provenance
    rebuilt = {**original, "feature_sha256": "0" * 64}

    assert snapshot_identity(original) != snapshot_identity(rebuilt)


def test_serving_snapshot_identity_includes_advisor_profile_content(tmp_path):
    import json
    import shutil
    from pathlib import Path

    from src.serving import MatchingService

    root = Path(__file__).parents[2]
    shutil.copytree(root / 'data/curated', tmp_path / 'data/curated')
    shutil.copytree(root / 'data/features', tmp_path / 'data/features')
    original = MatchingService(tmp_path)
    path = tmp_path / 'data/curated/advisors.json'
    advisors = json.loads(path.read_text(encoding='utf-8'))
    advisors[0]['advisor_name'] = 'Changed profile with same ID'
    path.write_text(json.dumps(advisors, ensure_ascii=False), encoding='utf-8')
    quality_path = tmp_path / 'data/curated/quality_report_v2.json'
    quality = json.loads(quality_path.read_text(encoding='utf-8'))
    quality['input_files']['data/curated/advisors.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    quality_path.write_text(json.dumps(quality, ensure_ascii=False), encoding='utf-8')
    changed = MatchingService(tmp_path)
    assert snapshot_identity(original.provenance) != snapshot_identity(changed.provenance)


def test_initialize_imports_validated_snapshot_and_split_idempotently(tmp_path) -> None:
    """Catches missing upserts or incomplete profile/split persistence."""
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE IF NOT EXISTS marker (id integer);", encoding="utf-8")
    connection = FakeConnection()
    storage = PostgresStorage("postgresql://example", schema, connect=lambda _dsn: connection)

    storage.initialize(_service())

    sql = "\n".join(query for query, _ in connection.calls)
    assert "CREATE TABLE IF NOT EXISTS marker" in sql
    assert sql.count("ON CONFLICT") >= 4
    imported = next(params for query, params in connection.calls if query.lstrip().startswith("INSERT INTO students"))
    memberships = next(
        params for query, params in connection.calls
        if query.lstrip().startswith("INSERT INTO split_memberships")
    )
    assert len(imported) == 2
    assert [(row[1], row[2], row[3]) for row in memberships] == [
        ("student-1", "train", 0),
        ("student-2", "validation", 0),
    ]


def test_initialize_creates_configured_schema_before_using_it(tmp_path) -> None:
    schema = tmp_path / "schema.sql"
    schema.write_text("", encoding="utf-8")
    connection = FakeConnection()
    storage = PostgresStorage(
        "postgresql://example",
        schema,
        schema_name="kltn_app",
        connect=lambda _dsn: connection,
    )

    storage.initialize(None)

    statements = [query for query, _ in connection.calls]
    assert statements[:2] == [
        'CREATE SCHEMA IF NOT EXISTS "kltn_app"',
        'SET search_path TO "kltn_app"',
    ]


def test_postgres_records_simulation_and_feedback_as_json(tmp_path) -> None:
    """Catches a successful API write being acknowledged without durable SQL."""
    schema = tmp_path / "schema.sql"
    schema.write_text("", encoding="utf-8")
    connection = FakeConnection()
    storage = PostgresStorage("postgresql://example", schema, connect=lambda _dsn: connection)

    storage.add_run(
        endpoint="simulate",
        mode="semantic",
        algorithm="hungarian",
        dataset="real-train",
        seed=42,
        snapshot_hash="d" * 64,
        result={"assignments": [{"student_id": "SV-TRAIN-001"}]},
    )
    storage.add_feedback(
        FeedbackRequest(mode="semantic", algorithm="hungarian", helpful=True),
        snapshot_hash="d" * 64,
    )

    run_params = next(params for query, params in connection.calls if "INSERT INTO simulation_runs" in query)
    feedback_params = next(params for query, params in connection.calls if "INSERT INTO feedback" in query)
    assert run_params[2:7] == ("simulate", "semantic", "hungarian", "real-train", 42)
    assert '"student_id":"SV-TRAIN-001"' in run_params[-1]
    assert feedback_params == ("d" * 64, "semantic", "hungarian", True)


def test_sqlite_initialize_imports_snapshot_idempotently(tmp_path) -> None:
    storage = SQLiteFeedbackStore(tmp_path)
    service = _service()

    storage.initialize(service)
    service.theses[0]["thesis_title"] = "Updated"
    storage.initialize(service)

    with sqlite3.connect(storage.path) as connection:
        counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("snapshots", "students", "advisors", "split_memberships")
        }
        profile = connection.execute(
            "SELECT profile FROM students WHERE student_id = ?", ("student-1",)
        ).fetchone()[0]
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    assert counts == {
        "snapshots": 1,
        "students": 2,
        "advisors": 1,
        "split_memberships": 2,
    }
    assert json.loads(profile)["thesis_title"] == "Updated"
    assert foreign_key_errors == []


def test_sqlite_run_and_feedback_survive_new_store_instance(tmp_path) -> None:
    service = _service()
    snapshot_hash = snapshot_identity(service.provenance)
    storage = SQLiteFeedbackStore(tmp_path)
    storage.initialize(service)
    storage.add_run(
        endpoint="simulate",
        mode="semantic",
        algorithm="hungarian",
        dataset="real-train",
        seed=42,
        snapshot_hash=snapshot_hash,
        result={"assignments": [{"student_id": "student-1"}]},
    )
    storage.add_feedback(
        FeedbackRequest(mode="semantic", algorithm="hungarian", helpful=True),
        snapshot_hash=snapshot_hash,
    )

    reopened = SQLiteFeedbackStore(tmp_path)
    reopened.initialize(service)

    with sqlite3.connect(reopened.path) as connection:
        run = connection.execute(
            "SELECT endpoint, seed, result FROM simulation_runs"
        ).fetchone()
        feedback = connection.execute(
            "SELECT snapshot_hash, helpful FROM feedback"
        ).fetchone()
    assert run[:2] == ("simulate", 42)
    assert '"student_id":"student-1"' in run[2]
    assert feedback == (snapshot_hash, 1)
    with pytest.raises(sqlite3.IntegrityError), sqlite3.connect(reopened.path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO simulation_runs(id, snapshot_hash, endpoint, mode, algorithm, dataset, seed, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("bad-run", "0" * 64, "simulate", "semantic", "greedy", "real-train", 1, "{}"),
        )


def test_sqlite_migrates_old_feedback_table_without_losing_rows(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE feedback (id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL, mode TEXT NOT NULL, algorithm TEXT NOT NULL, helpful INTEGER NOT NULL)"
        )
        connection.execute(
            "INSERT INTO feedback(created_at, mode, algorithm, helpful) VALUES (?, ?, ?, ?)",
            (1, "semantic", "greedy", 1),
        )

    SQLiteFeedbackStore(tmp_path).initialize(None)

    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(feedback)")}
        row = connection.execute(
            "SELECT created_at, mode, algorithm, helpful, snapshot_hash FROM feedback"
        ).fetchone()
    assert "snapshot_hash" in columns
    assert row == (1, "semantic", "greedy", 1, None)
