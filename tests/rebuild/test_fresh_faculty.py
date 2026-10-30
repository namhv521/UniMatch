import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    assert importlib.util.find_spec('src.data_pipeline.fresh_faculty'), 'fresh collector missing'
    return importlib.import_module('src.data_pipeline.fresh_faculty')


@pytest.mark.parametrize(('text', 'year', 'precision', 'value'), [
    ('Author (2024). A paper', 2024, 'year', None),
    ('Article published 30/06/2025', 2025, 'day', '2025-06-30'),
    ('Article published June 2025', 2025, 'month', '2025-06'),
    ('Article published 2025-12-03', 2025, 'day', '2025-12-03'),
    ('Article with no bibliographic date', None, 'unknown', None),
    ('Journal issue 6/2025', 2025, 'year', None),
    ('Author (2024). revised (2025)', None, 'ambiguous', None),
    ('Article 31/02/2025', None, 'invalid', None),
])
def test_date_precision_does_not_invent_month_or_day(text, year, precision, value):
    result = module().publication_date_evidence(text)
    assert result['publication_year'] == year
    assert result['date_precision'] == precision
    assert result['publication_date'] == value


def test_sitemap_filters_english_aliases_external_and_nonprofiles():
    body = b'<urlset><url><loc>https://fit.neu.edu.vn/lecturer/person</loc></url><url><loc>https://fit.neu.edu.vn/en/lecturer/person</loc></url><url><loc>https://example.org/lecturer/other</loc></url></urlset>'
    assert module().sitemap_profiles(body) == [{'source_url': 'https://fit.neu.edu.vn/lecturer/person', 'directory_name': None}]


PROFILE_URL = 'https://fit.neu.edu.vn/lecturer/sample'
DIRECTORY = b'<a href="/lecturer/sample"><h2>TS. Sample</h2></a>'
PROFILE = '''<div class="info-lecturer_name-content"><h1>TS. Sample</h1></div>
<div class="custom-h3"><h3>CÔNG TRÌNH KHOA HỌC</h3><ul>
<li>Author (2025). <a href="https://doi.org/10.1234/example">Paper title</a></li>
<li>Author (2024). Earlier paper</li></ul></div>'''.encode()


def fixture_fetch(url):
    values = {'https://fit.neu.edu.vn/robots.txt': b'User-agent: *\nAllow: /',
              'https://fit.neu.edu.vn/lecturer': DIRECTORY, PROFILE_URL: PROFILE}
    return values[url], 200, url


def test_fresh_collection_preserves_raw_publication_evidence_and_output(tmp_path):
    output = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    result = module().collect_faculty(output, fetcher=fixture_fetch, delay=0)
    assert result['faculty_count'] == 1 and result['publication_count'] == 2
    pubs = [json.loads(s) for s in (output / 'publications.jsonl').read_text(encoding='utf-8').splitlines()]
    assert pubs[0]['publication_year'] == 2025 and pubs[0]['publication_date'] is None
    assert pubs[0]['links'] == ['https://doi.org/10.1234/example']
    assert pubs[0]['historical_feature_available_at'] is None
    assert pubs[0]['source_sha256'] == hashlib.sha256(PROFILE).hexdigest()
    assert (output / 'raw' / (pubs[0]['source_sha256'] + '.html')).read_bytes() == PROFILE
    assert module().verify_collection(output)['publication_count'] == 2
    with pytest.raises(FileExistsError):
        module().collect_faculty(output, fetcher=fixture_fetch, delay=0)


def test_robot_blocked_profile_is_reported_and_never_fetched(tmp_path):
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith('robots.txt'):
            return b'User-agent: *\nDisallow: /lecturer/sample', 200, url
        return fixture_fetch(url)
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    result = module().collect_faculty(out, fetcher=fetch, delay=0)
    assert PROFILE_URL not in calls
    assert result['faculty_count'] == 1 and result['profile_failures'] == 1
    rows = [json.loads(s) for s in (out / 'faculty.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[0]['status'] == 'robots_disallowed'


def test_malformed_source_does_not_drop_directory_identity(tmp_path):
    def fetch(url):
        return (b'<h1>Website header</h1>', 200, url) if url == PROFILE_URL else fixture_fetch(url)
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    result = module().collect_faculty(out, fetcher=fetch, delay=0)
    assert result['faculty_count'] == 1 and result['publication_count'] == 0
    row = json.loads((out / 'faculty.jsonl').read_text(encoding='utf-8'))
    assert row['directory_name'] == 'TS. Sample' and row['advisor_name'] is None


def test_manifest_detects_tamper(tmp_path):
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    module().collect_faculty(out, fetcher=fixture_fetch, delay=0)
    (out / 'faculty.jsonl').write_text('{}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='collection_artifact_hash_mismatch'):
        module().verify_collection(out)


def test_output_must_be_separate_new_namespace(tmp_path):
    with pytest.raises(ValueError, match='new_nested_namespace_required'):
        module().collect_faculty(tmp_path / 'data_rebuild/v1/faculty', fetcher=fixture_fetch)
    with pytest.raises(ValueError, match='new_nested_namespace_required'):
        module().collect_faculty(tmp_path / 'data_rebuild/v1/nested_rl_20261028/run/faculty', fetcher=fixture_fetch)


def test_date_reparse_binds_fresh_source_manifest_and_keeps_original_unchanged(tmp_path):
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    m = module()
    m.collect_faculty(out, fetcher=fixture_fetch, delay=0)
    original_manifest = (out / 'manifest.json').read_bytes()
    original_pubs = (out / 'publications.jsonl').read_bytes()
    derived = out.parent / 'faculty_dates'
    result = m.reparse_publications(out, derived)
    assert result['publication_count'] == 2
    assert result['source_collection_manifest_sha256'] == hashlib.sha256(original_manifest).hexdigest()
    assert (out / 'manifest.json').read_bytes() == original_manifest
    assert (out / 'publications.jsonl').read_bytes() == original_pubs
    assert {p.name for p in derived.iterdir()} == {'publications.jsonl', 'date_validation_report.json', 'manifest.json'}
    assert m.verify_publication_dates(derived) == result
    with pytest.raises(FileExistsError):
        m.reparse_publications(out, derived)


def test_date_reparse_rejects_modified_fresh_inputs(tmp_path):
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    m = module()
    m.collect_faculty(out, fetcher=fixture_fetch, delay=0)
    (out / 'publications.jsonl').write_text('{}\n', encoding='utf-8')
    derived = out.parent / 'faculty_dates'
    with pytest.raises(ValueError, match='collection_artifact_hash_mismatch'):
        m.reparse_publications(out, derived)
    assert not derived.exists()

def test_external_scholar_collects_only_explicit_citation_year(tmp_path):
    m = module()
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    m.collect_faculty(out, fetcher=fixture_fetch, delay=0)
    rows = [json.loads(s) for s in (out / 'faculty.jsonl').read_text(encoding='utf-8').splitlines()]
    rows[0]['external_profiles'] = {'google_scholar': {'url': 'https://scholar.google.com/citations?user=test', 'identity_basis': 'owner_url_seed_only'}}
    m._jsonl(out / 'faculty.jsonl', rows)
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    manifest['artifacts']['faculty.jsonl'] = m._sha((out / 'faculty.jsonl').read_bytes())
    m._json(out / 'manifest.json', manifest)
    calls = []
    def fetch(url):
        calls.append(url)
        return (b'User-agent: *\nAllow: /', 200, url) if url.endswith('robots.txt') else (b'<tr class="gsc_a_tr"><td><a class="gsc_a_at" href="/citations?view_op=view_citation">Paper 2020 benchmark</a></td><td class="gsc_a_y"><span>2025</span></td></tr>', 200, url)
    target = out.parent / 'faculty_external'
    report = m.collect_external_profiles(out, target, fetcher=fetch, delay=0)
    assert report['profile_count'] == 1 and report['publication_count'] == 1
    pub = json.loads((target / 'publications.jsonl').read_text(encoding='utf-8'))
    assert pub['publication_year'] == 2025 and pub['publication_month'] is None
    assert pub['identity_basis'] == 'owner_url_seed_only'
    with pytest.raises(FileExistsError):
        m.collect_external_profiles(out, target, fetcher=fetch, delay=0)


def test_external_robots_block_preserves_attempt_without_fetching_profile(tmp_path):
    m = module()
    out = tmp_path / 'data_rebuild/nested_rl_20261028/run/faculty'
    m.collect_faculty(out, fetcher=fixture_fetch, delay=0)
    rows = [json.loads(s) for s in (out / 'faculty.jsonl').read_text(encoding='utf-8').splitlines()]
    rows[0]['external_profiles'] = {'researchgate': {'url': 'https://www.researchgate.net/profile/Test', 'identity_basis': 'fresh_official_profile_link'}}
    m._jsonl(out / 'faculty.jsonl', rows)
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    manifest['artifacts']['faculty.jsonl'] = m._sha((out / 'faculty.jsonl').read_bytes())
    m._json(out / 'manifest.json', manifest)
    calls = []
    def fetch(url):
        calls.append(url)
        return b'User-agent: *\nDisallow: /', 200, url
    target = out.parent / 'faculty_external'
    report = m.collect_external_profiles(out, target, fetcher=fetch, delay=0)
    assert report['publication_count'] == 0 and len(calls) == 1
    assert report['status_counts'] == {'robots_disallowed': 1}
    assert json.loads((target / 'profiles.jsonl').read_text(encoding='utf-8'))['fallback'] == 'official_fit_only'
