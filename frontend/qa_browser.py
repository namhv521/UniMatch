"""Optional browser smoke test against a running FastAPI server."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("KLTN_QA_BASE_URL", "http://127.0.0.1:4180")
EMAIL = os.environ["KLTN_QA_EMAIL"]
PASSWORD = os.environ["KLTN_QA_PASSWORD"]
OUTPUT = Path(__file__).with_name("qa-artifacts")
OUTPUT.mkdir(exist_ok=True)


with sync_playwright() as playwright:
    print(f"Browser executable: {playwright.chromium.executable_path}", flush=True)
    browser = playwright.chromium.launch(headless=True)
    print("Browser started", flush=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE_URL)
    print(f"Opened {BASE_URL}", flush=True)
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Mật khẩu").fill(PASSWORD)
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.get_by_role("heading", name="Năng lực gặp").wait_for()
    assert page.get_by_role("link", name="Phân bổ đợt sinh viên").is_visible()
    page.get_by_role("link", name="Khám phá mô phỏng").click()
    page.get_by_role("heading", name="Ghép cặp & mô phỏng thuật toán").wait_for()
    page.wait_for_function("document.querySelector('#dataset-select')?.value === 'real-train'")
    assert page.locator("#algorithm-select").input_value() == "hungarian"
    with page.expect_response(lambda response: response.url.endswith('/api/v1/simulate'), timeout=120000) as real_response:
        page.locator("#simulate").click()
    assert real_response.value.ok
    real_result = real_response.value.json()['data']
    train = page.request.get(BASE_URL + '/api/v1/datasets/real-train').json()['data']
    assert len(real_result['assignments']) == len(train['students'])
    assert real_result['metrics']['quota_violations'] == 0
    page.locator(f"#timeline[max='{len(train['students'])}']").wait_for()
    page.screenshot(path=str(OUTPUT / "real-train-desktop.png"), full_page=True)
    page.get_by_label("Dữ liệu").select_option("sample-3x2")
    page.get_by_role("button", name="Bắt đầu mô phỏng").click()
    page.get_by_text("SV01", exact=True).last.wait_for()
    page.get_by_role("button", name="Bước tiếp ›").click()
    assert page.locator("#step-count").inner_text().startswith("Bước 1/")
    assert page.locator("#event-panel dt").filter(has_text="Reward").count() == 0
    assert page.locator("#event-panel dd").first.inner_text() == "1"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(OUTPUT / "matching-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(OUTPUT / "matching-mobile.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.get_by_role("link", name="Kết quả").click()
    page.get_by_role("heading", name="Benchmark cùng protocol").wait_for()
    assert page.get_by_text("Engine: Hungarian").is_visible()
    assert page.get_by_role("heading", name="Checkpoint cho dữ liệu hiện tại").is_visible()
    with page.expect_response(lambda response: response.url.endswith('/api/v1/results/summary')):
        page.locator("#refresh-data").click()
    page.wait_for_function("!document.querySelector('#refresh-data')?.disabled")
    report = page.request.get(BASE_URL + '/api/v1/results/summary').json()['data']
    assert report['rows']
    assert all(set(row) <= {'algorithm', 'seed', 'metrics'} for row in report['rows'])
    page.screenshot(path=str(OUTPUT / "results-desktop.png"), full_page=True)
    page.get_by_role("link", name="Ghép cặp", exact=True).click()
    page.get_by_label("Dữ liệu").select_option("real-validation")
    page.locator('[data-mode="rl"]').click()
    catalog = page.request.get(BASE_URL + '/api/v1/catalog').json()['data']
    candidates = [model for model in catalog['models'] if model['algorithm'] == 'MaskablePPO'
                  and model['status'] == 'unpromoted_research' and model['seed'] == 42
                  and 'real-validation' in model['supported_datasets']]
    assert candidates, 'train a compatible current-snapshot MaskablePPO checkpoint first'
    selected = max(candidates, key=lambda model: model['completed_timesteps'])
    page.locator("#algorithm-select").select_option(selected['id'])
    with page.expect_response(lambda response: response.url.endswith('/api/v1/simulate'), timeout=120000) as simulation_response:
        page.locator("#simulate").click()
    response = simulation_response.value
    assert response.ok, response.json().get('error')
    validation = page.request.get(BASE_URL + '/api/v1/datasets/real-validation').json()['data']
    page.locator(f"#timeline[max='{len(validation['students'])}']").wait_for()
    page.locator("#next").click()
    assert page.locator("#event-panel dt").filter(has_text="Reward").count() == 1
    page.screenshot(path=str(OUTPUT / "research-desktop.png"), full_page=True)
    page.route("**/api/v1/auth/logout", lambda route: route.fulfill(status=503, json={"error":{"message":"Logout temporarily unavailable"}}))
    page.locator("#logout").click()
    assert page.locator("#logout").is_visible()
    assert page.get_by_role("alert").inner_text() == "Logout temporarily unavailable"
    assert page.evaluate("fetch('/api/v1/auth/session').then(r=>r.json()).then(r=>(r.data ?? r).authenticated)") is True
    page.unroute("**/api/v1/auth/logout")
    page.locator("#logout").click()
    page.get_by_role("button", name="Đăng nhập", exact=True).wait_for()
    assert not errors, errors
    browser.close()

print(f"PASS: desktop/mobile matching and results; screenshots={OUTPUT}")
