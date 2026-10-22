"""Official faculty evidence crawl. Public source text never establishes quotas or consent."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

import bs4
from bs4 import BeautifulSoup


DIRECTORY_URL = 'https://fit.neu.edu.vn/lecturer'
ROBOTS_URL = 'https://fit.neu.edu.vn/robots.txt'
USER_AGENT = 'UniMatchSourceAudit/1.0'
PARSER_VERSION = 'lecturer-crawl/1.1'


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _text(node) -> str:
    return ' '.join(node.get_text(' ', strip=True).split()) if node is not None else ''


def _timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('source_timestamp_requires_timezone')
    return value


def _profile_url(value: str, base_url: str = DIRECTORY_URL) -> str | None:
    url = urlsplit(urljoin(base_url, value))
    if (url.scheme != 'https' or url.netloc != 'fit.neu.edu.vn'
            or not re.fullmatch(r'/lecturer/[^/?#]+', url.path)
            or '%' in url.path or '\\' in url.path or url.path.rsplit('/', 1)[-1] in {'.', '..'}):
        return None
    return urlunsplit((url.scheme, url.netloc, url.path, '', ''))


def parse_directory(html: str | bytes, base_url: str = DIRECTORY_URL) -> list[dict]:
    if base_url.rstrip('/') != DIRECTORY_URL:
        raise ValueError('directory_url_out_of_scope')
    soup = BeautifulSoup(html, 'html.parser')
    entries = {}
    for anchor in soup.find_all('a', href=True):
        url = _profile_url(anchor['href'], base_url)
        if not url:
            continue
        name_node = anchor.select_one('h2, .adjunct-name')
        role_node = anchor.select_one('.position')
        name = _text(name_node) or None
        role = _text(role_node) or None
        item = entries.setdefault(url, {'source_url': url, 'directory_name': None, 'directory_role': None,
                                         'directory_snippet': '', 'directory_aliases': []})
        if name:
            if item['directory_name'] and name != item['directory_name']:
                item['directory_aliases'].append(name)
            else:
                item['directory_name'] = name
        if role:
            item['directory_role'] = role
        snippet = _text(anchor)
        if len(snippet) > len(item['directory_snippet']):
            item['directory_snippet'] = snippet
    return list(entries.values())


def parse_profile(html: str | bytes, url: str, retrieved_at: str, content_sha256: str,
                  directory_entry: dict | None = None) -> dict:
    if _profile_url(url) != url:
        raise ValueError('profile_url_out_of_scope')
    _timestamp(retrieved_at)
    raw = html.encode('utf-8') if isinstance(html, str) else html
    if _sha(raw) != content_sha256:
        raise ValueError('content_hash_mismatch')
    soup = BeautifulSoup(raw, 'html.parser')
    for node in soup(['script', 'style', 'noscript']):
        node.decompose()
    directory_entry = directory_entry or {}
    name_node = soup.select_one('.info-lecturer_name-content h1')
    name = _text(name_node) or None
    evidence = []

    def add(field, snippet, locator):
        if snippet:
            evidence.append({'field': field, 'snippet': snippet, 'locator': locator,
                             'source_url': url, 'retrieved_at': retrieved_at,
                             'source_sha256': content_sha256, 'evidence_type': 'verified_web'})

    add('advisor_name', name, '.info-lecturer_name-content h1')
    intro_node = soup.select_one('.info-lecturer_content')
    intro_parts, contacts = [], []
    if intro_node:
        after_contact = False
        for child in intro_node.children:
            if getattr(child, 'name', None) in {'h3', 'h4'} and 'LIÊN HỆ' in _text(child).upper():
                after_contact = True
                continue
            text = _text(child) if getattr(child, 'name', None) else str(child).strip()
            if text:
                (contacts if after_contact else intro_parts).append(text)
    intro = ' '.join(intro_parts)
    add('profile_intro', intro, '.info-lecturer_content > before LIÊN HỆ')
    sections = {'teaching_topics': [], 'research_topics': [], 'publications': [], 'research_projects': []}
    headings = {'GIẢNG DẠY': 'teaching_topics', 'LĨNH VỰC NGHIÊN CỨU': 'research_topics',
                'CÔNG TRÌNH KHOA HỌC': 'publications',
                'CÔNG TRÌNH KHOA HỌC TIÊU BIỂU': 'publications',
                'CÁC BÀI BÁO KHOA HỌC, BÀI THAM LUẬN HỘI THẢO ĐÃ CÔNG BỐ': 'publications',
                'CÔNG TRÌNH NGHIÊN CỨU KHOA HỌC ĐÃ CÔNG BỐ': 'publications',
                'CÔNG TRÌNH KHOA HỌC ĐÃ CÔNG BỐ': 'publications',
                'CÔNG TRÌNH NGHIÊN CỨU ĐÃ CÔNG BỐ': 'publications',
                'CÁC CÔNG TRÌNH NGHIÊN CỨU ĐÃ CÔNG': 'publications',
                'CÔNG TRÌNH NGHIÊN CỨU': 'research_projects',
                'CÁC ĐỀ TÀI NGHIÊN CỨU KHOA HỌC': 'research_projects',
                'CÁC ĐỀ TÀI NGHIÊN CỨU KHOA': 'research_projects',
                'ĐỀ TÀI NGHIÊN CỨU': 'research_projects'}
    for heading in soup.select('.custom-h3 h3, .custom-list h3'):
        label = unicodedata.normalize('NFC', _text(heading)).upper().rstrip(' :：')
        field = headings.get(label)
        if not field:
            continue
        for sibling in heading.next_siblings:
            if getattr(sibling, 'name', None) in {'h2', 'h3'}:
                break
            if not getattr(sibling, 'name', None):
                continue
            items = sibling.find_all('li') if sibling.name in {'ul', 'ol'} else [sibling]
            for index, item in enumerate(items, 1):
                text = _text(item)
                if text and text not in sections[field]:
                    sections[field].append(text)
                    add(field, text, f'section[{label}] item[{index}]')
    reasons = ['human_review_required', 'semester_participation_and_capacity_unconfirmed']
    if not name:
        reasons.append('missing_profile_name')
    if not sections['research_topics']:
        reasons.append('missing_explicit_research_topics')
    if not sections['publications']:
        reasons.append('missing_publications')
    directory_name = directory_entry.get('directory_name')
    normalize_name = lambda value: re.sub(r'\W+', '', unicodedata.normalize('NFC', value).casefold())
    if name and directory_name and normalize_name(name) != normalize_name(directory_name):
        reasons.append('directory_profile_name_disagreement')
    profile_text = '\n'.join(part for part in [intro, *sections['teaching_topics'],
                                                 *sections['research_topics'], *sections['publications'],
                                                 *sections['research_projects']] if part)
    return {'schema_version': '1.0', 'advisor_id': 'fit_' + _sha(url.encode())[:20],
            'advisor_name': name, 'source_type': 'official_web', 'source_url': url,
            'retrieved_at': retrieved_at, 'source_sha256': content_sha256,
            'parser_version': PARSER_VERSION, 'beautifulsoup_version': bs4.__version__,
            'directory_name': directory_name, 'directory_role': directory_entry.get('directory_role'),
            'directory_aliases': directory_entry.get('directory_aliases', []),
            'profile_intro': intro or None, **sections, 'profile_text': profile_text or None,
            'contacts_attribution_only': contacts, 'affiliation': None,
            'expertise_topic_tags': [], 'technology_tags': [], 'expertise_proficiency_json': None,
            'active_for_semester': None, 'capacity_max': None, 'existing_load': None,
            'evidence': evidence, 'review_status': 'needs_review', 'review_reasons': reasons,
            'status': 'extracted' if name else 'quarantined'}


def _require_phase1(output: Path) -> tuple[dict, str]:
    gate_path = output / 'reports/phase1_gate.json'
    gate = json.loads(gate_path.read_text(encoding='utf-8'))
    if gate.get('status') != 'verified' or not gate.get('can_start_phase2'):
        raise ValueError('phase1_not_verified')
    run_id = gate.get('run_id', '')
    if not run_id or Path(run_id).name != run_id:
        raise ValueError('phase1_run_identity_missing')
    run = output / 'phase1_runs' / run_id
    try:
        manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        entry = next(a for a in manifest['artifacts'] if a['path'].replace('\\', '/') == 'reports/phase1_gate.json')
        if (manifest['gate'] != gate or entry['sha256'] != _digest(gate_path)
                or _digest(run / 'reports/phase1_gate.json') != _digest(gate_path)
                or gate['input_inventory_sha256'] != _digest(output / 'reports/input_inventory.csv')):
            raise ValueError('phase1_artifact_binding_mismatch')
    except (OSError, KeyError, StopIteration) as exc:
        raise ValueError('phase1_artifact_binding_missing') from exc
    return gate, _digest(gate_path)


class _ScopedRedirects(HTTPRedirectHandler):
    def __init__(self, allowed):
        super().__init__()
        self.allowed = allowed

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl not in self.allowed:
            raise HTTPError(req.full_url, code, 'redirect_out_of_scope', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(url: str, allowed: set[str]) -> tuple[bytes, int, str]:
    opener = build_opener(_ScopedRedirects(allowed))
    request = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        response = opener.open(request, timeout=25)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(5 * 1024 * 1024 + 1)
        if len(body) > 5 * 1024 * 1024:
            raise ValueError('html_response_size_limit')
        return body, response.code, response.url


def _csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row)) or ['source_url', 'status', 'reason']
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _cached_responses(run: Path, directory_hash: str):
    """Reparse immutable HTTP receipts without claiming a fresh network retrieval."""
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['gate']['directory_sha256'] != directory_hash:
        raise ValueError('cached_directory_identity_mismatch')
    for artifact in manifest['artifacts']:
        path = run / artifact['path']
        if run not in path.resolve().parents or _digest(path) != artifact['sha256']:
            raise ValueError('cached_artifact_checksum_mismatch')
    cached = {}
    for line in (run / 'bronze/faculty_pages.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row.get('status') != 'fetched':
            continue
        path = Path(row['raw_path']).resolve()
        if run not in path.parents or _digest(path) != row['source_sha256']:
            raise ValueError('cached_raw_checksum_mismatch')
        cached[row['source_url']] = (path.read_bytes(), row['http_status'], row['source_url'], row['retrieved_at'])

    def fetch(url):
        if url not in cached:
            raise ValueError('cached_response_missing')
        return cached[url]

    return fetch


def crawl_faculty(output: Path, directory_capture: Path, *, delay: float = 1.0,
                  retries: int = 2, fetcher=None, cache_run: Path | None = None) -> dict:
    output, directory_capture = Path(output).resolve(), Path(directory_capture).resolve()
    phase1, phase1_hash = _require_phase1(output)
    capture_hash = _digest(directory_capture)
    capture = json.loads(directory_capture.read_text(encoding='utf-8'))
    if capture.get('url', '').rstrip('/') != DIRECTORY_URL:
        raise ValueError('directory_capture_url_out_of_scope')
    if _sha(capture['html'].encode('utf-8')) != capture.get('sha256'):
        raise ValueError('directory_capture_checksum_mismatch')
    _timestamp(capture['retrieved_at'])
    entries = parse_directory(capture['html'])
    if not entries:
        raise ValueError('directory_capture_has_no_profile_links')
    if cache_run is not None:
        if fetcher is not None:
            raise ValueError('cache_and_fetcher_are_mutually_exclusive')
        cache_run = Path(cache_run).resolve()
        fetcher = _cached_responses(cache_run, capture['sha256'])
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run = output / 'phase2_runs' / run_id
    for name in ('raw_index', 'bronze', 'silver', 'reports'):
        (run / name).mkdir(parents=True, exist_ok=False)
    code_hash = _digest(Path(__file__))
    raw_pages, advisors, quality, review = [], [], [], []
    allowed = {ROBOTS_URL, *[entry['source_url'] for entry in entries]}
    last_request = 0.0

    def fetch(url):
        nonlocal last_request
        last = None
        for attempt in range(retries + 1):
            time.sleep(max(0, delay - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            row = {'source_url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                   'parser_version': PARSER_VERSION, 'attempt': attempt + 1, 'status': 'failed', 'reason': ''}
            try:
                fetched = fetcher(url) if fetcher else _http_get(url, allowed)
                body, status, final_url = fetched[:3]
                if len(fetched) == 4:
                    row['retrieved_at'] = _timestamp(fetched[3])
                    row['retrieval_method'] = 'cached_raw_reparse'
                if final_url != url:
                    raise ValueError('profile_redirect_requires_review')
                path = run / 'raw_index' / (_sha(url.encode()) + '-' + _sha(body) + '.html')
                path.write_bytes(body)
                row.update(http_status=status, source_sha256=_sha(body), raw_path=str(path),
                           status='fetched' if status == 200 else 'failed',
                           reason='' if status == 200 else f'http_{status}')
                raw_pages.append(row)
                if status == 200 or status not in {429, 500, 502, 503, 504}:
                    return body, row
            except Exception as exc:
                row['reason'] = type(exc).__name__ + (':' + str(exc) if isinstance(exc, ValueError) else '')
                raw_pages.append(row)
            last = row
            if attempt < retries:
                time.sleep(min(8, 2**attempt))
        return None, last

    directory_raw = run / 'raw_index/directory_rendered.html'
    directory_raw.write_bytes(capture['html'].encode('utf-8'))
    directory_provenance = {'source_url': DIRECTORY_URL, 'retrieved_at': capture['retrieved_at'],
                            'source_sha256': capture['sha256'], 'raw_path': str(directory_raw),
                            'capture_method': capture.get('capture_method', 'provided_rendered_html')}
    robots_body, robots_record = fetch(ROBOTS_URL)
    robots = RobotFileParser()
    if robots_body is not None and robots_record['status'] == 'fetched':
        robots.parse(robots_body.decode('utf-8', errors='replace').splitlines())
    for index, entry in enumerate(entries, 1):
        url = entry['source_url']
        failure = None
        if robots_body is None or robots_record['status'] != 'fetched':
            failure = 'robots_unavailable'
        elif not robots.can_fetch(USER_AGENT, url):
            failure = 'robots_disallowed'
        if failure:
            quality.append({'source_url': url, 'status': 'failed', 'reason': failure})
            review.append({'source_url': url, 'reason': failure})
            continue
        body, record = fetch(url)
        if body is None or record['status'] != 'fetched':
            quality.append({'source_url': url, 'status': 'failed', 'reason': record['reason']})
            review.append({'source_url': url, 'reason': record['reason']})
            continue
        try:
            advisor = parse_profile(body, url, record['retrieved_at'], record['source_sha256'], entry)
            advisor['directory_provenance'] = directory_provenance
            advisors.append(advisor)
            quality.append({'source_url': url, 'advisor_id': advisor['advisor_id'], 'status': advisor['status'],
                            'reason': ';'.join(advisor['review_reasons']), 'research_topics': len(advisor['research_topics']),
                            'publications': len(advisor['publications']), 'source_sha256': advisor['source_sha256']})
            review.extend({'source_url': url, 'advisor_id': advisor['advisor_id'], 'reason': reason}
                          for reason in advisor['review_reasons'])
        except Exception as exc:
            quality.append({'source_url': url, 'status': 'failed', 'reason': type(exc).__name__})
            review.append({'source_url': url, 'reason': type(exc).__name__})
        if index % 5 == 0:
            print(json.dumps({'phase': 2, 'profiles_processed': index, 'total': len(entries)}), flush=True)
    names = defaultdict(list)
    for advisor in advisors:
        if advisor['advisor_name']:
            names[unicodedata.normalize('NFC', advisor['advisor_name']).casefold()].append(advisor)
    for group in names.values():
        if len(group) > 1:
            for advisor in group:
                advisor['review_reasons'].append('same_name_multiple_profile_urls')
                review.append({'source_url': advisor['source_url'], 'reason': 'same_name_multiple_profile_urls'})
    for name, records in [('bronze/faculty_pages.jsonl', [directory_provenance, *raw_pages]),
                          ('silver/advisors.jsonl', advisors)]:
        with (run / name).open('w', encoding='utf-8') as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    _csv(run / 'reports/advisor_crawl_quality.csv', quality)
    _csv(run / 'reports/advisor_review_queue.csv', review)
    failures = sum(row['status'] != 'extracted' for row in quality)
    unchanged = code_hash == _digest(Path(__file__)) and phase1_hash == _digest(output / 'reports/phase1_gate.json') and capture_hash == _digest(directory_capture)
    verified = len(quality) == len(entries) and not failures and unchanged
    report = {'phase': 2, 'status': 'verified' if verified else 'blocked', 'can_start_phase3': verified,
              'scope': 'Official profile source coverage/provenance; not semester eligibility, quotas or gold approval',
              'run_id': run_id, 'run_dir': str(run), 'directory_profiles': len(entries),
              'included_advisors': len(advisors), 'fetch_failures': failures, 'human_approved_records': 0,
              'missing_research_topics': sum(not advisor['research_topics'] for advisor in advisors),
              'missing_publications': sum(not advisor['publications'] for advisor in advisors),
              'directory_sha256': capture['sha256'], 'input_phase1_gate_sha256': phase1_hash,
              'cache_source_run': str(cache_run) if cache_run else None,
              'source_code_sha256': code_hash, 'code_and_inputs_unchanged': unchanged,
              'parser_version': PARSER_VERSION, 'beautifulsoup_version': bs4.__version__,
              'created_at': datetime.now(timezone.utc).isoformat()}
    (run / 'reports/phase2_gate.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (run / 'manifest.json').write_text(json.dumps({'gate': report, 'artifacts': [
        {'path': str(path.relative_to(run)), 'sha256': _digest(path)} for parent in ('raw_index', 'bronze', 'silver', 'reports')
        for path in sorted((run / parent).iterdir()) if path.is_file()]}, indent=2), encoding='utf-8')
    for parent in ('bronze', 'silver', 'reports'):
        (output / parent).mkdir(exist_ok=True)
        for path in (run / parent).iterdir():
            shutil.copy2(path, output / parent / path.name)
    return report
