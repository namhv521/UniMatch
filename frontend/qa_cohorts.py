"""Browser integration for the synthetic 38-student cohort flow."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parents[1]
ACCESS_FILE = Path(os.getenv("KLTN_QA_ACCESS_FILE", ROOT / "outputs/runtime/local-web-20261015.json"))
FIXTURE = Path(os.getenv("KLTN_QA_COHORT_FILE", ROOT / "outputs/final_validation/cohort-ui-smoke-38.xlsx"))
OUTPUT = Path(__file__).with_name("qa-artifacts")
OUTPUT.mkdir(exist_ok=True)


def access() -> tuple[str, str, str]:
    saved = json.loads(ACCESS_FILE.read_text(encoding="utf-8-sig")) if ACCESS_FILE.exists() else {}
    return (
        os.getenv("KLTN_QA_BASE_URL", saved.get("base_url", "http://127.0.0.1:8000")),
        os.getenv("KLTN_QA_EMAIL", saved.get("email", "")),
        os.getenv("KLTN_QA_PASSWORD", saved.get("password", "")),
    )


base_url, email, password = access()
assert email and password, "Set KLTN_QA_EMAIL/KLTN_QA_PASSWORD or provide KLTN_QA_ACCESS_FILE"
assert FIXTURE.is_file(), f"Synthetic fixture is missing: {FIXTURE}"

invalid_path: Path | None = None
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(f"{base_url}/#/login")
        page.get_by_label("Email").fill(email)
        page.get_by_label("Mật khẩu").fill(password)
        page.get_by_role("button", name="Đăng nhập", exact=True).click()
        page.get_by_role("heading", name="Kết nối đúng người.").wait_for()

        page.get_by_role("link", name="Nhập sinh viên").click()
        page.get_by_role("heading", name="Nhập sinh viên theo kỳ").wait_for()
        advisor_inputs = page.locator('.advisor-checklist input[name="advisor"]')
        assert advisor_inputs.count() == 38
        assert page.locator('.advisor-checklist input[name="advisor"]:checked').count() == 0
        assert page.locator("#allocate-cohort").is_disabled()

        with page.expect_download() as download_info:
            page.get_by_role("link", name="Tải file Excel mẫu").click()
        assert download_info.value.suggested_filename.endswith(".xlsx")

        with page.expect_response(lambda response: response.url.endswith("/api/v1/student-cohorts/preview")) as preview_info:
            page.locator("#student-file").set_input_files(str(FIXTURE))
        assert preview_info.value.ok
        page.get_by_text("38 sinh viên hợp lệ", exact=False).wait_for()
        assert page.locator(".cohort-table tbody tr").count() == 38
        survey_fixture = page.locator(".cohort-table details").count() > 0
        if survey_fixture:
            assert set(page.locator(".cohort-table tbody td:nth-child(3)").all_inner_texts()) == {"—"}
            assert page.locator(".cohort-table details").count() == 38
            page.locator(".cohort-table details summary").first.click()
            assert "Python: 2" in page.locator(".cohort-table details").first.inner_text()
        assert page.locator("#allocate-cohort").is_disabled()

        search = page.locator("#advisor-search")
        search.fill("pham minh hoan")
        pham_label = page.locator(".advisor-checklist label").filter(has_text="TS PHẠM MINH HOÀN")
        assert pham_label.count() == 1
        selected_names = [pham_label.locator("strong").inner_text()]
        pham_label.locator("input").check()
        search.fill("")
        other_ids = page.locator('.advisor-checklist input[name="advisor"]:not(:checked)').evaluate_all(
            "inputs => inputs.slice(0, 3).map(input => input.value)"
        )
        for advisor_id in other_ids:
            candidate_input = page.locator(f'.advisor-checklist input[value="{advisor_id}"]')
            selected_names.append(candidate_input.locator("xpath=..").locator("strong").inner_text())
            candidate_input.check()

        assert page.locator('.advisor-checklist input[name="advisor"]:checked').count() == 4
        quota_rows = page.locator(".quota-list span")
        assert quota_rows.count() == 4
        quota_values = quota_rows.evaluate_all(
            "rows => rows.map(row => Number(row.lastChild.textContent.match(/\\d+/)[0]))"
        )
        assert quota_values == [10, 10, 9, 9]

        with page.expect_response(lambda response: "/api/v1/student-cohorts/allocate?" in response.url, timeout=120_000) as allocation_info:
            page.locator("#allocate-cohort").click()
        assert allocation_info.value.ok
        page.get_by_role("heading", name="Kết quả phân bổ").wait_for()
        assert page.locator(".cohort-result tbody tr").count() == 38
        assert page.locator(".advisor-loads article").count() == 4
        rendered_names = page.locator(".advisor-loads strong").all_inner_texts()
        assert set(rendered_names) == set(selected_names)
        assert [int(text.split("/")[0].strip()) for text in page.locator(".advisor-loads span").all_inner_texts()] == [10, 10, 9, 9]
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(OUTPUT / "cohorts-desktop.png"), full_page=True)

        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(OUTPUT / "cohorts-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})

        page.locator(f'.advisor-checklist input[value="{other_ids[0]}"]').uncheck()
        assert page.get_by_role("heading", name="Kết quả phân bổ").count() == 0
        page.locator("#clear-advisors").click()
        assert page.locator('.advisor-checklist input[name="advisor"]:checked').count() == 0
        assert page.locator("#allocate-cohort").is_disabled()

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as invalid:
            invalid.write(b"not an xlsx workbook")
            invalid_path = Path(invalid.name)
        with page.expect_response(lambda response: response.url.endswith("/api/v1/student-cohorts/preview")) as invalid_info:
            page.locator("#student-file").set_input_files(str(invalid_path))
        assert invalid_info.value.status >= 400
        page.get_by_role("alert").wait_for()
        assert page.get_by_role("alert").inner_text().strip()
        assert page.locator("#allocate-cohort").is_disabled()
        assert page.locator(".cohort-table").count() == 0
        assert not errors, errors
    finally:
        browser.close()
        if invalid_path:
            invalid_path.unlink(missing_ok=True)

print(f"PASS: synthetic cohort upload/allocation desktop+mobile; screenshots={OUTPUT}")
