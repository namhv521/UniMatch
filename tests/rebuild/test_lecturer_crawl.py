import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


NOW = '2026-10-21T15:00:00+00:00'
DIRECTORY = 'https://fit.neu.edu.vn/lecturer'
PROFILE = DIRECTORY + '/lecturer-example'
HTML = '''<html><h1>Faculty website header</h1>
<div class="info-lecturer_name-content"><h1>TS. GIẢNG VIÊN MẪU</h1><h3>GIỚI THIỆU</h3></div>
<div class="info-lecturer_content"><div>Nghiên cứu hệ thống thông tin.</div><h4>LIÊN HỆ</h4><p>sample@example.test</p><p>0900000000</p></div>
<div class="custom-h3 custom-list"><h3>GIẢNG DẠY</h3><ul><li>Cơ sở dữ liệu</li></ul>
<h3>LĨNH VỰC NGHIÊN CỨU</h3><ol><li>Học máy ứng dụng</li></ol>
<h3>GIẢI THƯỞNG VÀ VINH DANH</h3><ol><li>Giải thưởng mẫu</li></ol>
<h3>CÔNG TRÌNH KHOA HỌC</h3><ol><li>Bài báo kỹ thuật mẫu (2024)</li></ol></div></html>'''
DIRECTORY_HTML = '''<a href="/lecturer/lecturer-example"><img src="a.jpg"></a>
<a class="lecturer-name-link" href="/lecturer/lecturer-example"><div class="card-body"><h2>TS GIẢNG VIÊN MẪU</h2><h3 class="position">Giảng viên</h3></div></a>
<a href="/api/private">forbidden</a><a href="https://other.example/lecturer/foreign">foreign</a>
<a href="/lecturer/not-allowed/deeper">invalid depth</a>'''


def module():
    path = Path(__file__).resolve().parents[2] / 'src/data_pipeline/lecturer_crawl.py'
    assert path.exists(), 'Lecturer crawler implementation missing'
    spec = importlib.util.spec_from_file_location('lecturer_crawl', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def prepared(tmp_path):
    output = tmp_path / 'output'
    reports = output / 'reports'
    reports.mkdir(parents=True)
    inventory = reports / 'input_inventory.csv'
    inventory.write_text('fixture inventory', encoding='utf-8')
    run = output / 'phase1_runs' / 'accepted-fixture'
    (run / 'reports').mkdir(parents=True)
    gate = {'status': 'verified', 'can_start_phase2': True, 'run_id': run.name, 'run_dir': str(run),
            'input_inventory_sha256': hash_bytes(inventory.read_bytes())}
    encoded = json.dumps(gate).encode()
    (reports / 'phase1_gate.json').write_bytes(encoded)
    (run / 'reports/phase1_gate.json').write_bytes(encoded)
    (run / 'manifest.json').write_text(json.dumps({'gate': gate, 'artifacts': [
        {'path': 'reports/phase1_gate.json', 'sha256': hash_bytes(encoded)}]}), encoding='utf-8')
    capture = tmp_path / 'directory.json'
    capture.write_text(json.dumps({'html': DIRECTORY_HTML, 'url': DIRECTORY, 'retrieved_at': NOW,
                                    'sha256': hash_bytes(DIRECTORY_HTML.encode())}), encoding='utf-8')
    return output, capture


def test_directory_scope_deduplicates_image_and_name_links():
    records = module().parse_directory(DIRECTORY_HTML)
    assert len(records) == 1
    assert records[0]['source_url'] == PROFILE
    assert records[0]['directory_name'] == 'TS GIẢNG VIÊN MẪU'
    assert records[0]['directory_role'] == 'Giảng viên'


def test_profile_sections_are_evidence_not_contact_or_website_header():
    helper = module()
    record = helper.parse_profile(HTML, PROFILE, NOW, hash_bytes(HTML.encode()), helper.parse_directory(DIRECTORY_HTML)[0])
    assert record['advisor_name'] == 'TS. GIẢNG VIÊN MẪU'
    assert record['research_topics'] == ['Học máy ứng dụng']
    assert record['teaching_topics'] == ['Cơ sở dữ liệu']
    assert record['publications'] == ['Bài báo kỹ thuật mẫu (2024)']
    assert 'sample@example.test' not in record['profile_text']
    assert '0900000000' not in record['profile_text']
    assert 'Giải thưởng mẫu' not in record['profile_text']
    assert record['capacity_max'] is None and record['active_for_semester'] is None
    assert record['expertise_topic_tags'] == []
    assert record['review_status'] == 'needs_review'
    assert all(e['source_url'] == PROFILE and e['source_sha256'] == hash_bytes(HTML.encode()) for e in record['evidence'])
    assert record['advisor_id'] == helper.parse_profile(HTML, PROFILE, NOW, hash_bytes(HTML.encode()))['advisor_id']


def test_profile_missing_fields_and_hash_mismatch_are_explicit():
    helper = module()
    html = '<h1>Website header only</h1>'
    record = helper.parse_profile(html, PROFILE, NOW, hash_bytes(html.encode()))
    assert record['advisor_name'] is None
    assert record['research_topics'] == []
    assert 'missing_profile_name' in record['review_reasons']
    with pytest.raises(ValueError, match='content_hash_mismatch'):
        helper.parse_profile(HTML, PROFILE, NOW, '0' * 64)


@pytest.mark.parametrize('heading', ['CÔNG TRÌNH KHOA HỌC TIÊU BIỂU:',
    'CÁC BÀI BÁO KHOA HỌC, BÀI THAM LUẬN HỘI THẢO ĐÃ CÔNG BỐ',
    'CÔNG TRÌNH NGHIÊN CỨU KHOA HỌC ĐÃ CÔNG BỐ'])
def test_observed_publication_heading_variants_keep_evidence(heading):
    html = HTML.replace('CÔNG TRÌNH KHOA HỌC', heading).replace('LĨNH VỰC NGHIÊN CỨU', 'LĨNH VỰC NGHIÊN CỨU:')
    record = module().parse_profile(html, PROFILE, NOW, hash_bytes(html.encode()))
    assert record['publications'] == ['Bài báo kỹ thuật mẫu (2024)']
    assert record['research_topics'] == ['Học máy ứng dụng']
    assert any(heading.rstrip(':') in e['locator'] for e in record['evidence'] if e['field'] == 'publications')


def test_crawl_requires_bound_phase1_and_capture_checksum(tmp_path):
    output, capture = prepared(tmp_path)
    helper = module()
    bad = json.loads(capture.read_text())
    bad['html'] += '<a href="/lecturer/forged">forged</a>'
    capture.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='directory_capture_checksum_mismatch'):
        helper.crawl_faculty(output, capture, delay=0, retries=0)
    assert not (output / 'phase2_runs').exists()
    bad['sha256'] = hash_bytes(bad['html'].encode())
    capture.write_text(json.dumps(bad), encoding='utf-8')
    (output / 'reports/phase1_gate.json').write_text('{"status":"verified","can_start_phase2":true}', encoding='utf-8')
    with pytest.raises(ValueError, match='phase1'):
        helper.crawl_faculty(output, capture, delay=0, retries=0)


def test_crawl_records_robots_and_never_fetches_disallowed_profiles(tmp_path):
    output, capture = prepared(tmp_path)
    seen = []

    def fetch(url):
        seen.append(url)
        assert url == 'https://fit.neu.edu.vn/robots.txt'
        return b'User-agent: *\nDisallow: /lecturer/\nDisallow: /api/\n', 200, url

    report = module().crawl_faculty(output, capture, delay=0, retries=0, fetcher=fetch)
    assert report['status'] == 'blocked'
    assert seen == ['https://fit.neu.edu.vn/robots.txt']
    assert report['fetch_failures'] == 1


def test_crawl_snapshots_source_evidence_and_reports_http_failure(tmp_path):
    output, capture = prepared(tmp_path)
    helper = module()
    phase1_manifest = output / 'phase1_runs/accepted-fixture/manifest.json'
    manifest = json.loads(phase1_manifest.read_text(encoding='utf-8'))
    manifest['artifacts'][0]['path'] = 'reports\\phase1_gate.json'
    phase1_manifest.write_text(json.dumps(manifest), encoding='utf-8')

    def fetch(url):
        if url.endswith('/robots.txt'):
            return b'User-agent: *\nAllow: /\nDisallow: /api/\n', 200, url
        assert url == PROFILE
        return HTML.encode(), 200, url

    report = helper.crawl_faculty(output, capture, delay=0, retries=0, fetcher=fetch)
    assert report['status'] == 'verified' and report['can_start_phase3'] is True
    assert report['included_advisors'] == 1
    advisors = [json.loads(line) for line in (Path(report['run_dir']) / 'silver/advisors.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(advisors) == 1 and advisors[0]['source_url'] == PROFILE
    assert advisors[0]['directory_provenance']['source_sha256'] == hash_bytes(DIRECTORY_HTML.encode())
    for line in (Path(report['run_dir']) / 'bronze/faculty_pages.jsonl').read_text(encoding='utf-8').splitlines():
        page = json.loads(line)
        if page.get('raw_path') and page.get('source_sha256'):
            assert hash_bytes(Path(page['raw_path']).read_bytes()) == page['source_sha256']
    assert report['human_approved_records'] == 0
    cached = helper.crawl_faculty(output, capture, delay=0, retries=0, cache_run=Path(report['run_dir']))
    assert cached['status'] == 'verified'
    cached_records = [json.loads(line) for line in (Path(cached['run_dir']) / 'silver/advisors.jsonl').read_text(encoding='utf-8').splitlines()]
    assert cached_records[0]['retrieved_at'] == advisors[0]['retrieved_at']

    def failed(url):
        return (b'User-agent: *\nAllow: /', 200, url) if url.endswith('/robots.txt') else (b'Unavailable', 503, url)

    report = helper.crawl_faculty(output, capture, delay=0, retries=0, fetcher=failed)
    assert report['status'] == 'blocked' and report['fetch_failures'] == 1
    assert report['included_advisors'] == 0
