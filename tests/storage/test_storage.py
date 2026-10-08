from __future__ import annotations

import hashlib
from types import SimpleNamespace

from backend.app.schemas import FeedbackRequest
from backend.app.storage import PostgresStorage, snapshot_identity


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
