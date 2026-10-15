from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.storage import snapshot_identity

ROOT = Path(__file__).parents[2]
ORIGIN = "http://testserver"


class RecordingStorage:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.initialized = []
        self.runs = []
        self.feedback = []

    def initialize(self, service) -> None:
        if self.error:
            raise self.error
        self.initialized.append(service)

    def add_run(self, **run) -> None:
        self.runs.append(run)

    def add_feedback(self, feedback, *, snapshot_hash: str) -> None:
        self.feedback.append((feedback, snapshot_hash))


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "local@example.test", "password": "password"},
    )
    assert response.status_code == 200


def test_lifespan_initializes_storage_and_persists_api_writes(monkeypatch, tmp_path) -> None:
    """Catches API success paths that forget database initialization or writes."""
    monkeypatch.setenv("KLTN_LOGIN_EMAIL", "local@example.test")
    monkeypatch.setenv("KLTN_LOGIN_PASSWORD", "password")
    monkeypatch.setenv("KLTN_COOKIE_SECURE", "false")
    storage = RecordingStorage()
    app = create_app(root=ROOT, runtime_dir=tmp_path, storage=storage)

    with TestClient(app) as client:
        _login(client)
        simulated = client.post(
            "/api/v1/simulate",
            headers={"Origin": ORIGIN},
            json={"mode": "semantic", "algorithm": "hungarian", "dataset": "sample-2x2", "seed": 7},
        )
        feedback = client.post(
            "/api/v1/feedback",
            headers={"Origin": ORIGIN},
            json={"mode": "semantic", "algorithm": "hungarian", "helpful": True},
        )

    assert simulated.status_code == feedback.status_code == 200
    assert len(storage.initialized) == 1
    assert storage.runs[0]["endpoint"] == "simulate"
    assert storage.runs[0]["seed"] == 7
    assert storage.feedback[0][1] == snapshot_identity(storage.initialized[0].provenance)


def test_configured_storage_failure_aborts_startup(tmp_path) -> None:
    """Catches silent fallback when a configured PostgreSQL service is unavailable."""
    app = create_app(root=ROOT, runtime_dir=tmp_path, storage=RecordingStorage(RuntimeError("database unavailable")))

    with pytest.raises(RuntimeError, match="database unavailable"), TestClient(app):
        pass


def test_results_summary_uses_current_artifact_and_dynamic_snapshot_counts(monkeypatch, tmp_path) -> None:
    """Catches valid current benchmarks being rejected by stale fixed row counts."""
    monkeypatch.setenv("KLTN_LOGIN_EMAIL", "local@example.test")
    monkeypatch.setenv("KLTN_LOGIN_PASSWORD", "password")
    monkeypatch.setenv("KLTN_COOKIE_SECURE", "false")
    storage = RecordingStorage()
    app = create_app(root=ROOT, runtime_dir=tmp_path, storage=storage)
    service = app.state.service
    benchmark = tmp_path / "current-validation.json"
    benchmark.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("backend.app.main._benchmark_path", lambda _root: benchmark)
    provenance = {
        "dataset_hash": service.provenance["dataset_sha256"],
        "feature_hash": service.provenance["feature_sha256"],
        "split_hash": service.provenance["split_sha256"],
        "advisor_mapping_hash": service.provenance["advisor_order_sha256"],
        "capacity_policy": "uniform-ceiling-experimental-v1",
        "split": "validation",
    }
    monkeypatch.setattr(
        "backend.app.main.json_load",
        lambda _path: {
            "schema_version": "1.0",
            "split": "validation",
            "students": len(service.split["indices"]["validation"]),
            "advisors": len(service.advisors),
            "provenance": provenance,
            "summary": [],
        },
    )

    with TestClient(app) as client:
        _login(client)
        response = client.get("/api/v1/results/summary")

    assert response.status_code == 200
    assert response.json()["data"]["students"] == len(service.split["indices"]["validation"])


def test_results_summary_ignores_legacy_benchmark_when_current_is_missing(monkeypatch, tmp_path) -> None:
    """Catches stale historical results being presented as current evidence."""
    monkeypatch.setenv("KLTN_LOGIN_EMAIL", "local@example.test")
    monkeypatch.setenv("KLTN_LOGIN_PASSWORD", "password")
    monkeypatch.setenv("KLTN_COOKIE_SECURE", "false")
    monkeypatch.setattr("backend.app.main._benchmark_path", lambda _root: tmp_path / "missing.json")
    app = create_app(root=ROOT, runtime_dir=tmp_path, storage=RecordingStorage())

    with TestClient(app) as client:
        _login(client)
        response = client.get("/api/v1/results/summary")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "not_evaluated"


def test_default_sqlite_store_persists_api_run_and_feedback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KLTN_LOGIN_EMAIL", "local@example.test")
    monkeypatch.setenv("KLTN_LOGIN_PASSWORD", "password")
    monkeypatch.setenv("KLTN_COOKIE_SECURE", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = create_app(root=ROOT, runtime_dir=tmp_path)

    with TestClient(app) as client:
        _login(client)
        assert client.post(
            "/api/v1/simulate",
            headers={"Origin": ORIGIN},
            json={"mode": "semantic", "algorithm": "hungarian", "dataset": "sample-2x2", "seed": 7},
        ).status_code == 200
        assert client.post(
            "/api/v1/feedback",
            headers={"Origin": ORIGIN},
            json={"mode": "semantic", "algorithm": "hungarian", "helpful": True},
        ).status_code == 200

    with sqlite3.connect(tmp_path / "feedback.sqlite3") as connection:
        run = connection.execute(
            "SELECT endpoint, algorithm, seed FROM simulation_runs"
        ).fetchone()
        feedback = connection.execute(
            "SELECT algorithm, helpful FROM feedback"
        ).fetchone()
    assert run == ("simulate", "hungarian", 7)
    assert feedback == ("hungarian", 1)
