from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app

ROOT = Path(__file__).parents[2]
ORIGIN = "http://testserver"


def _client(monkeypatch, tmp_path: Path, *, secure: bool = False) -> TestClient:
    monkeypatch.setenv("KLTN_LOGIN_EMAIL", "local@example.test")
    monkeypatch.setenv("KLTN_LOGIN_PASSWORD", "correct horse battery staple")
    monkeypatch.setenv("KLTN_COOKIE_SECURE", "true" if secure else "false")
    return TestClient(create_app(root=ROOT, runtime_dir=tmp_path))


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "local@example.test", "password": "correct horse battery staple"},
    )
    assert response.status_code == 200


def test_private_api_requires_server_side_session(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/v1/catalog")

    assert response.status_code == 401
    assert response.json() == {"status": "error", "error": {"code": "authentication_required", "message": "Authentication required"}}


def test_login_fails_closed_when_credentials_are_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KLTN_LOGIN_EMAIL", raising=False)
    monkeypatch.delenv("KLTN_LOGIN_PASSWORD", raising=False)
    client = TestClient(create_app(root=ROOT, runtime_dir=tmp_path))

    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "anything@example.test", "password": "anything"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_not_configured"


def test_password_is_compared_verbatim_without_whitespace_normalization(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "local@example.test", "password": "correct horse battery staple "},
    )

    assert response.status_code == 401


def test_login_session_logout_and_cookie_flags(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)

    _login(client)
    cookie = client.cookies.get("kltn_session")
    assert cookie
    set_cookie = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "local@example.test", "password": "correct horse battery staple"},
    ).headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie

    session = client.get("/api/v1/auth/session")
    assert session.json() == {"authenticated": True, "user": {"display_name": "Người dùng cục bộ"}}
    assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 200
    assert client.get("/api/v1/catalog").status_code == 401


def test_cross_origin_writes_are_rejected(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _login(client)

    response = client.post(
        "/api/v1/simulate",
        headers={"Origin": "https://attacker.invalid"},
        json={"mode": "semantic", "algorithm": "greedy", "dataset": "sample-3x2", "seed": 42},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_rejected"


def test_authenticated_api_contract_and_privacy(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _login(client)

    catalog = client.get("/api/v1/catalog")
    dataset = client.get("/api/v1/datasets/real-validation")
    simulated = client.post(
        "/api/v1/simulate",
        headers={"Origin": ORIGIN},
        json={"mode": "semantic", "algorithm": "hungarian", "dataset": "real-validation", "seed": 42},
    )
    recommended = client.post(
        "/api/v1/recommend",
        headers={"Origin": ORIGIN},
        json={"title": "Xử lý ngôn ngữ tự nhiên", "top_k": 3},
    )

    assert catalog.status_code == dataset.status_code == simulated.status_code == recommended.status_code == 200
    assert catalog.json()["status"] == "success"
    assert {item["id"] for item in catalog.json()["data"]["datasets"]} >= {
        "real-train", "real-validation",
    }
    assert "real-test" not in {item["id"] for item in catalog.json()["data"]["datasets"]}
    assert client.get("/api/v1/datasets/real-test").status_code == 400
    assert simulated.json()["data"]["events"][0].keys() >= {
        "step", "student_id", "advisor_id", "student_index", "advisor_index", "score", "reward",
        "loads_before", "loads_after", "capacities", "invalid_proposal", "fallback", "explanation",
    }
    body = json.dumps([catalog.json(), dataset.json(), simulated.json(), recommended.json()], ensure_ascii=False)
    assert "11181231" not in body
    assert "C:\\" not in body
    assert "http" not in body.lower()


def test_feedback_is_bounded_structured_data(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _login(client)

    response = client.post(
        "/api/v1/feedback",
        headers={"Origin": ORIGIN},
        json={"mode": "semantic", "algorithm": "greedy", "helpful": True},
    )

    assert response.status_code == 200
    assert response.json()["data"]["stored"] is True
    assert (tmp_path / "feedback.sqlite3").is_file()


def test_benchmark_summary_rejects_stale_provenance(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _login(client)
    benchmark = json.loads((ROOT / "outputs/benchmarks/validation-2026-10-07.json").read_text(encoding="utf-8"))
    benchmark_path = tmp_path / 'benchmark.json'
    benchmark_path.write_text('{}')
    monkeypatch.setattr('backend.app.main._benchmark_path', lambda _root: benchmark_path)
    benchmark["provenance"]["feature_hash"] = "0" * 64
    monkeypatch.setattr("backend.app.main.json_load", lambda _path: benchmark)

    response = client.get("/api/v1/benchmark/summary")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "benchmark_unverified"


def test_static_frontend_is_mounted_after_api_routes(monkeypatch, tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<h1>KLTN</h1>", encoding="utf-8")
    client = _client(monkeypatch, tmp_path)
    app = create_app(root=ROOT, runtime_dir=tmp_path, frontend_dir=frontend)
    client = TestClient(app)

    assert client.get("/").text == "<h1>KLTN</h1>"
    health = client.get("/api/v1/health").json()
    assert health["status"] == ("healthy" if health["quality_ready"] else "degraded")
    assert health["data_loaded"] is True
    assert health["total_advisors"] == 38


def test_health_is_degraded_instead_of_false_ready_when_artifacts_missing(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(create_app(root=tmp_path / "missing", runtime_dir=tmp_path / "runtime"))

    health = client.get("/api/v1/health")

    assert health.status_code == 200
    assert health.json() == {
        "status": "degraded",
        "version": "1.0.0",
        "data_loaded": False,
        "quality_ready": False,
        "total_advisors": 0,
        "available_models": [],
    }


def test_validation_errors_do_not_leak_input_or_paths(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    _login(client)
    secret = "SECRET-PII-TEXT"

    response = client.post(
        "/api/v1/recommend",
        headers={"Origin": ORIGIN},
        json={"title": secret * 100, "top_k": 999},
    )

    assert response.status_code == 422
    body = response.text
    assert secret not in body
    assert str(ROOT) not in body
