from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.cohorts import CohortError
from backend.app.main import _read_limited_body, create_app

ROOT = Path(__file__).parents[2]
ORIGIN = "http://testserver"
SCHEMA = json.loads((ROOT / "configs/student_upload_schema.json").read_text(encoding="utf-8"))
HEADERS = [column["key"] for column in SCHEMA["columns"]]


def workbook_bytes(count: int) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "SinhVien"
    sheet.append(HEADERS)
    for index in range(1, count + 1):
        row = {
            "student_id": f"UPLOAD-{index:03}",
            "student_name": f"Sinh viên upload {index}",
            "thesis_title": f"Đề tài dữ liệu {index}",
            "app_languages": "Python",
            "ai_problems": "Machine Learning",
        }
        sheet.append([row.get(key) for key in HEADERS])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def corrupt_sheet_xml(content: bytes) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(content))
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            payload = source.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                payload = b"<worksheet><broken>"
            target.writestr(entry, payload)
    return output.getvalue()


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "local@example.test", "password": "password"},
    )
    assert response.status_code == 200


def client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("KLTN_LOGIN_EMAIL", "local@example.test")
    monkeypatch.setenv("KLTN_LOGIN_PASSWORD", "password")
    monkeypatch.setenv("KLTN_COOKIE_SECURE", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return TestClient(create_app(root=ROOT, runtime_dir=tmp_path))


def test_cohort_routes_require_session_and_origin(monkeypatch, tmp_path) -> None:
    with client(monkeypatch, tmp_path) as api:
        assert api.get("/api/v1/student-cohorts/advisors").status_code == 401
        login(api)
        assert api.post("/api/v1/student-cohorts/preview", content=workbook_bytes(1)).status_code == 403


def test_advisors_and_preview_expose_authenticated_real_data(monkeypatch, tmp_path) -> None:
    with client(monkeypatch, tmp_path) as api:
        login(api)
        advisors = api.get("/api/v1/student-cohorts/advisors")
        preview = api.post(
            "/api/v1/student-cohorts/preview",
            headers={"Origin": ORIGIN, "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            content=workbook_bytes(1),
        )

    assert advisors.status_code == preview.status_code == 200
    assert len(advisors.json()["data"]["advisors"]) == 38
    assert {"id", "name", "primary_field"} == set(advisors.json()["data"]["advisors"][0])
    assert any(row["name"] == "TS PHẠM MINH HOÀN" for row in advisors.json()["data"]["advisors"])
    assert preview.json()["data"]["student_count"] == 1


def test_missing_template_returns_503_instead_of_crashing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("backend.app.main._template_path", lambda _root: tmp_path / "missing.xlsx")
    with client(monkeypatch, tmp_path) as api:
        login(api)
        response = api.get("/api/v1/student-cohorts/template")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "template_unavailable"


def test_allocate_persists_complete_balanced_result_in_sqlite(monkeypatch, tmp_path) -> None:
    with client(monkeypatch, tmp_path) as api:
        login(api)
        advisor_rows = api.get("/api/v1/student-cohorts/advisors").json()["data"]["advisors"][:4]
        response = api.post(
            "/api/v1/student-cohorts/allocate",
            params=[("advisor_ids", row["id"]) for row in advisor_rows],
            headers={"Origin": ORIGIN, "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            content=workbook_bytes(38),
        )

    assert response.status_code == 200
    result = response.json()["data"]
    assert [row["quota"] for row in result["advisors"]] == [10, 10, 9, 9]
    assert len(result["assignments"]) == 38
    assert len(result["source_sha256"]) == len(result["cohort_hash"]) == 64
    assert result["provenance"]["source_sha256"] == result["source_sha256"]

    with sqlite3.connect(tmp_path / "feedback.sqlite3") as connection:
        run = connection.execute(
            "SELECT endpoint, mode, algorithm, dataset, result FROM simulation_runs"
        ).fetchone()
    assert run[:3] == ("allocate", "semantic", "hungarian-balanced-v1")
    assert run[3] == f"uploaded-{result['cohort_hash']}"
    stored = json.loads(run[4])
    assert stored["assignments"] == result["assignments"]
    assert stored["selected_advisor_ids"] == [row["id"] for row in advisor_rows]
    assert stored["cohort"]["students"][0].keys() >= {
        "student_id", "student_name", "thesis_title", "abstract", "app_languages",
        "ai_problems", "skills", "feature_text",
    }
    assert stored["provenance"]["advisor_snapshot"]["advisor_order_sha256"]


def test_allocate_rejects_duplicate_selected_advisors_with_vietnamese_error(monkeypatch, tmp_path) -> None:
    with client(monkeypatch, tmp_path) as api:
        login(api)
        advisor_id = api.get("/api/v1/student-cohorts/advisors").json()["data"]["advisors"][0]["id"]
        response = api.post(
            "/api/v1/student-cohorts/allocate",
            params=[("advisor_ids", advisor_id), ("advisor_ids", advisor_id)],
            headers={"Origin": ORIGIN},
            content=workbook_bytes(1),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cohort"
    assert "bị trùng" in response.json()["error"]["message"]


def test_chunked_preview_aborts_after_file_limit_without_content_length(monkeypatch, tmp_path) -> None:
    def chunks():
        yield b"x" * (3 * 1024 * 1024)
        yield b"y" * (3 * 1024 * 1024)

    with client(monkeypatch, tmp_path) as api:
        login(api)
        response = api.post(
            "/api/v1/student-cohorts/preview",
            headers={"Origin": ORIGIN, "Transfer-Encoding": "chunked"},
            content=chunks(),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_bounded_stream_reader_stops_before_consuming_later_chunks() -> None:
    import asyncio

    consumed: list[int] = []

    class StreamingRequest:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        async def stream(self):
            for position, chunk in enumerate((b"a" * 4, b"b" * 4, b"c" * 4), start=1):
                consumed.append(position)
                yield chunk

    with pytest.raises(CohortError) as raised:
        asyncio.run(_read_limited_body(StreamingRequest(), 5))
    assert raised.value.code == "file_too_large"
    assert consumed == [1, 2]


def test_corrupt_sheet_xml_returns_422_api_error(monkeypatch, tmp_path) -> None:
    with client(monkeypatch, tmp_path) as api:
        login(api)
        response = api.post(
            "/api/v1/student-cohorts/preview",
            headers={"Origin": ORIGIN},
            content=corrupt_sheet_xml(workbook_bytes(1)),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cohort"

