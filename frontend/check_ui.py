"""Local browser checks with explicit synthetic API fixtures, never research results."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'qa-artifacts'
OUTPUT.mkdir(exist_ok=True)
handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT.parent / 'backend/app/static'))
server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
advisor = {'advisor_id': 'demo-advisor', 'advisor_name': 'Giảng viên minh họa', 'primary_field': 'Hệ thống thông tin'}
fixture = {'status': 'success', 'algorithm': 'exact_hungarian', 'partial_data': True,
           'metrics': {'mean_compatibility': .8, 'quota_violations': 0, 'optimality_ratio': 1, 'load_variance': 0},
           'assignments': [{'student_id': 'DEMO', 'student_name': 'Sinh viên minh họa', 'thesis_title': 'Dữ liệu giả lập chỉ dùng kiểm tra giao diện', 'advisor_name': advisor['advisor_name'], 'compatibility_score': .8}],
           'advisor_loads': {advisor['advisor_name']: {'current_load': 1, 'quota': 1, 'ratio': 1}}}

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def api(route):
            name = route.request.url.rsplit('/', 1)[-1]
            payload = {'health': {'data_loaded': True, 'partial_data': True, 'available_models': ['exact_hungarian'], 'total_advisors': 1}, 'faculty': {'advisors': [advisor]}, 'allocate': fixture}[name]
            route.fulfill(content_type='application/json', body=json.dumps(payload))
        page.route('**/api/v1/*', api)
        page.goto(f'http://127.0.0.1:{server.server_port}')
        page.get_by_role('button', name='Chạy phân bổ').click()
        page.get_by_text('Sinh viên minh họa', exact=True).wait_for()
        assert page.get_by_text('Đã đủ hạn mức', exact=True).count() == 1
        assert page.get_by_text('Dữ liệu đang hoàn thiện.', exact=True).count() == 1
        for width, height, name in [(1440, 1000, 'desktop'), (390, 844, 'mobile')]:
            page.set_viewport_size({'width': width, 'height': height})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), name
            page.screenshot(path=str(OUTPUT / f'{name}.png'), full_page=True)
        page.get_by_role('searchbox').fill('not-present')
        page.get_by_text('Không có kết quả phù hợp. Thử từ khóa khác.').wait_for()
        page.route('**/api/v1/allocate', lambda route: route.fulfill(status=422, content_type='application/json', body=json.dumps({'detail':'Insufficient capacity'})))
        page.get_by_role('button', name='Chạy phân bổ').click()
        page.get_by_role('alert').filter(has_text='Insufficient capacity').wait_for()
        page.route('**/api/v1/health', lambda route: route.fulfill(content_type='application/json', body=json.dumps({'data_loaded':False,'partial_data':None,'available_models':[]})))
        page.get_by_role('button', name='Tải lại dữ liệu').click()
        page.get_by_text('Dữ liệu chưa sẵn sàng.', exact=False).wait_for()
        assert page.get_by_role('button', name='Chạy phân bổ').is_disabled()
        assert not errors, errors
        browser.close()
        print('PASS: allocation, partial warning, full quota, search, error, unavailable data, desktop/mobile overflow, no browser errors')
finally:
    server.shutdown()
