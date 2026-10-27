"""Fresh official faculty/publication snapshots for the nested-RL rebuild.

Existing URL lists are discovery seeds only. No old raw, gold, publication data
or prior approvals are consumed. Publication dates never imply historical input
availability or personal proficiency.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .lecturer_crawl import DIRECTORY_URL, ROBOTS_URL, _profile_url, parse_directory, parse_profile


USER_AGENT = 'UniMatchResearch/2.0'
VERSION = 'fresh-faculty/1.1'
SITEMAP_URL = 'https://fit.neu.edu.vn/sitemap.xml'
MAX_BYTES = 5 * 1024 * 1024


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def publication_date_evidence(text):
    """Keep observed precision. Conflicting/invalid dates remain unresolved."""
    base = {'publication_year': None, 'publication_month': None, 'publication_date': None,
            'date_precision': 'unknown', 'date_evidence': [], 'date_status': 'missing'}
    days = []
    patterns = [(r'\b((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})\b', 'ymd'),
                (r'\b(\d{1,2})[/.](\d{1,2})[/.]((?:19|20)\d{2})\b', 'dmy')]
    for pattern, order in patterns:
        for match in re.finditer(pattern, text):
            values = list(map(int, match.groups()))
            y, m, d = values if order == 'ymd' else values[::-1]
            try:
                value = date(y, m, d).isoformat()
            except ValueError:
                return {**base, 'date_precision': 'invalid', 'date_status': 'invalid', 'date_evidence': [match.group()]}
            days.append((value, match.group()))
    if days:
        unique = {row[0] for row in days}
        if len(unique) != 1:
            return {**base, 'date_precision': 'ambiguous', 'date_status': 'conflicting', 'date_evidence': [v[1] for v in days]}
        value = days[0][0]
        return {**base, 'publication_year': int(value[:4]), 'publication_month': int(value[5:7]),
                'publication_date': value, 'date_precision': 'day', 'date_status': 'observed',
                'date_evidence': [v[1] for v in days]}
    months = []
    for match in re.finditer(r'(?<![\d/])(0?[1-9]|1[0-2])[/.-]((?:19|20)\d{2})(?!\d)', text):
        # A journal issue such as "6/2025" is not evidence of June.
        context = text[max(0, match.start() - 24):match.start()]
        if re.search(r'(?:tháng|month|published|publication\s+date|ngày\s+xuất\s+bản)\s*[:=-]?\s*$', context, re.I):
            months.append((int(match[2]), int(match[1]), match.group()))
    names = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december')
    for match in re.finditer(r'\b(' + '|'.join(names) + r')\s+((?:19|20)\d{2})\b', text, re.I):
        months.append((int(match[2]), names.index(match[1].lower()) + 1, match.group()))
    for match in re.finditer(r'tháng\s+(0?[1-9]|1[0-2])\s*[,/.-]?\s*(?:năm\s*)?((?:19|20)\d{2})', text, re.I):
        months.append((int(match[2]), int(match[1]), match.group()))
    if months:
        unique = {(y, m) for y, m, _ in months}
        if len(unique) != 1:
            return {**base, 'date_precision': 'ambiguous', 'date_status': 'conflicting', 'date_evidence': [r[2] for r in months]}
        y, m = next(iter(unique))
        return {**base, 'publication_year': y, 'publication_month': m, 'publication_date': f'{y:04d}-{m:02d}',
                'date_precision': 'month', 'date_status': 'observed', 'date_evidence': [r[2] for r in months]}
    # Prefer bibliographic parenthesized years; title/data years are not promoted
    # when several candidates remain. The original text is always retained.
    matches = list(re.finditer(r'\((?:19|20)\d{2}\)', text))
    if not matches:
        matches = list(re.finditer(r'\b(?:19|20)\d{2}\b', text))
    years = {int(re.search(r'\d{4}', m.group())[0]) for m in matches}
    if len(years) == 1:
        return {**base, 'publication_year': next(iter(years)), 'date_precision': 'year',
                'date_status': 'observed_year_only', 'date_evidence': [m.group() for m in matches]}
    if years:
        return {**base, 'date_precision': 'ambiguous', 'date_status': 'conflicting', 'date_evidence': [m.group() for m in matches]}
    return base


def sitemap_profiles(body):
    xml = ElementTree.fromstring(body)
    urls = sorted({node.text.strip() for node in xml.iter() if node.tag.split('}')[-1] == 'loc'
                   and node.text and _profile_url(node.text.strip()) == node.text.strip()})
    return [{'source_url': url, 'directory_name': None} for url in urls]


class _OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.hostname != 'fit.neu.edu.vn' or parsed.path.startswith('/api/'):
            raise ValueError('redirect_outside_official_public_scope')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _live_fetch(url):
    opener = build_opener(_OfficialRedirects())
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Cache-Control': 'no-cache'})
    try:
        response = opener.open(request, timeout=25)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('source_response_size_limit')
        return body, response.code, response.url


def _external_platform(url):
    parsed = urlsplit(url)
    host, path = (parsed.hostname or '').lower(), parsed.path.rstrip('/')
    if parsed.scheme not in ('https', 'http'):
        return None
    if host in ('scholar.google.com', 'scholar.google.com.vn') and path == '/citations' and parse_qs(parsed.query).get('user'):
        return 'google_scholar'
    if host in ('researchgate.net', 'www.researchgate.net') and re.fullmatch(r'/profile/[^/]+', path):
        return 'researchgate'
    if host in ('github.com', 'www.github.com') and re.fullmatch(r'/[A-Za-z0-9][A-Za-z0-9-]*', path):
        return 'github'
    return None


def collect_faculty(output, seed_csv=None, directory_html=None, *, delay=1.0, retries=2, fetcher=None):
    output = Path(output).resolve()
    parts = output.parts
    if len(parts) < 4 or parts[-4] != 'data_rebuild' or parts[-3] != 'nested_rl_20261028' or output.name != 'faculty':
        raise ValueError('new_nested_namespace_required')
    if output.exists():
        raise FileExistsError('fresh_output_already_exists')
    output.mkdir(parents=True)
    (output / 'raw').mkdir()
    fetcher = fetcher or _live_fetch
    sources, profiles, publications = [], [], []
    last_request = 0.0

    def get(url, kind):
        nonlocal last_request
        for attempt in range(retries + 1):
            time.sleep(max(0, delay - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            row = {'url': url, 'kind': kind, 'attempt': attempt + 1,
                   'retrieved_at': datetime.now(timezone.utc).isoformat(), 'retrieval': 'fresh_network',
                   'status': 'failed', 'http_status': None, 'sha256': None, 'raw_path': None, 'error': None}
            try:
                body, code, final_url = fetcher(url)
                if len(body) > MAX_BYTES:
                    raise ValueError('source_response_size_limit')
                if urlsplit(final_url).hostname != 'fit.neu.edu.vn':
                    raise ValueError('source_redirect_host_mismatch')
                sha = _sha(body)
                path = output / 'raw' / (sha + '.html')
                path.write_bytes(body)
                row.update(http_status=code, final_url=final_url, sha256=sha, raw_path=path.relative_to(output).as_posix(),
                           status='fetched' if code == 200 else 'http_error', size_bytes=len(body))
                sources.append(row)
                if code in (200, 404):
                    return body, row
                if code in (401, 403):
                    return body, row
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
                sources.append(row)
        return b'', row

    robots_body, robots_source = get(ROBOTS_URL, 'robots')
    robots = RobotFileParser(ROBOTS_URL)
    if robots_source['http_status'] == 200:
        robots.parse(robots_body.decode('utf-8', errors='replace').splitlines())
    elif robots_source['http_status'] == 404:
        robots.parse(['User-agent: *', 'Allow: /'])
    else:
        robots.parse(['User-agent: *', 'Disallow: /'])
    entries, directory_source = [], None
    if robots.can_fetch(USER_AGENT, DIRECTORY_URL):
        body, directory_source = get(DIRECTORY_URL, 'directory')
        if directory_source['http_status'] == 200:
            entries = parse_directory(body)
    if not entries and directory_html:
        # Caller supplies a fresh browser-rendered capture, not a prior raw page.
        capture = json.loads(Path(directory_html).read_text(encoding='utf-8-sig'))
        if capture.get('url') != DIRECTORY_URL or not capture.get('retrieved_at') or capture.get('sha256') != _sha(capture['html'].encode()):
            raise ValueError('fresh_directory_capture_binding_required')
        timestamp = datetime.fromisoformat(capture['retrieved_at'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None or abs((datetime.now(timezone.utc) - timestamp).total_seconds()) > 3600:
            raise ValueError('fresh_directory_capture_must_be_within_one_hour')
        body = capture['html'].encode()
        path = output / 'raw' / (capture['sha256'] + '.html')
        path.write_bytes(body)
        sources.append({'url': DIRECTORY_URL, 'kind': 'rendered_directory', 'retrieved_at': capture['retrieved_at'],
                        'retrieval': 'fresh_browser_capture', 'sha256': capture['sha256'], 'raw_path': path.relative_to(output).as_posix(),
                        'status': 'fetched', 'http_status': 200})
        entries = parse_directory(body)
    if not entries and robots.can_fetch(USER_AGENT, SITEMAP_URL):
        body, source = get(SITEMAP_URL, 'sitemap_directory_discovery')
        if source['http_status'] == 200:
            try:
                entries = sitemap_profiles(body)
            except ElementTree.ParseError:
                pass
    seeds = {}
    if seed_csv:
        with Path(seed_csv).open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row.get('FIT NEU'):
                    seeds[row['FIT NEU']] = {kind: row.get(column, '').strip() for kind, column in
                        [('google_scholar', 'Google Scholar'), ('github', 'GitHub'), ('researchgate', 'ResearchGate')]}
    for entry in entries:
        url = entry['source_url']
        if not robots.can_fetch(USER_AGENT, url):
            profiles.append({**entry, 'advisor_id': 'fit_' + _sha(url.encode())[:20], 'advisor_name': None,
                             'status': 'robots_disallowed', 'review_status': 'needs_review', 'publications': []})
            continue
        body, source = get(url, 'official_profile')
        if source['http_status'] != 200:
            profiles.append({**entry, 'advisor_id': 'fit_' + _sha(url.encode())[:20], 'advisor_name': None,
                             'status': 'fetch_failed', 'review_status': 'needs_review', 'publications': [], 'source_receipt': source})
            continue
        profile = parse_profile(body, url, source['retrieved_at'], source['sha256'], entry)
        soup = BeautifulSoup(body, 'html.parser')
        external = {kind: {'url': value or None, 'identity_basis': 'owner_url_seed_only' if value else 'missing',
                           'content_fetched': False} for kind, value in seeds.get(url, {}).items()}
        for kind in ('google_scholar', 'github', 'researchgate'):
            external.setdefault(kind, {'url': None, 'identity_basis': 'missing', 'content_fetched': False})
        for anchor in soup.find_all('a', href=True):
            link = urljoin(url, anchor['href'])
            kind = _external_platform(link)
            if kind:
                external[kind] = {'url': link, 'identity_basis': 'fresh_official_profile_link', 'content_fetched': False}
        profile.update(external_profiles=external, collection_version=VERSION, historical_feature_available_at=None,
                       fresh_source=True, collection_scope='official_profile_and_publication_list')
        profiles.append(profile)
        for index, text in enumerate(profile['publications']):
            refs = [ref for ref in profile['evidence'] if ref['field'] == 'publications' and ref['snippet'] == text]
            nodes = [node for node in soup.find_all(['li', 'p']) if ' '.join(node.get_text(' ', strip=True).split()) == text]
            links = sorted({urljoin(url, anchor['href']) for node in nodes for anchor in node.find_all('a', href=True)
                            if urlsplit(urljoin(url, anchor['href'])).scheme in ('https', 'http')})
            identity = profile['advisor_id'] + '\0' + text
            publications.append({'publication_id': 'pub_' + _sha(identity.encode())[:24],
                'advisor_id': profile['advisor_id'], 'title_text': text, 'text': text,
                'source_url': url, 'source_sha256': source['sha256'], 'retrieved_at': source['retrieved_at'],
                'locator': refs[0]['locator'] if refs else f'publication[{index + 1}]', 'evidence': refs,
                **publication_date_evidence(text), 'links': links, 'review_status': 'needs_review',
                'historical_feature_available_at': None, 'personal_proficiency': None,
                'collection_scope': 'publication_text_observed_on_fresh_official_profile'})
    date_counts = Counter(row['date_precision'] for row in publications)
    report = {'schema_version': VERSION, 'collection_status': 'collected' if entries else 'blocked_directory_discovery',
              'fresh_network_collection': True, 'faculty_count': len(profiles), 'publication_count': len(publications),
              'profile_failures': sum(row['status'] != 'extracted' for row in profiles),
              'date_precision_counts': dict(date_counts), 'source_attempts': len(sources),
              'external_content_fetched': False, 'historical_training_ready': False,
              'limitations': ['Publication year does not establish historical feature availability.',
                  'Official publications are observed claims; missing dates remain unresolved.',
                  'External profile URL seeds are not reused old content; external content has not been fetched.']}
    _jsonl(output / 'sources.jsonl', sources)
    _jsonl(output / 'faculty.jsonl', profiles)
    _jsonl(output / 'publications.jsonl', publications)
    _json(output / 'collection_report.json', report)
    artifacts = {p.relative_to(output).as_posix(): _sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
    _json(output / 'manifest.json', {'schema_version': VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
          'artifacts': artifacts, 'collector_sha256': _sha(Path(__file__).read_bytes()),
          'seed_csv_sha256': _sha(Path(seed_csv).read_bytes()) if seed_csv else None})
    verify_collection(output)
    return report


def verify_collection(output):
    output = Path(output).resolve()
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['artifacts'].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output) or not path.is_file() or _sha(path.read_bytes()) != expected:
            raise ValueError('collection_artifact_hash_mismatch: ' + name)
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    if actual != set(manifest['artifacts']):
        raise ValueError('collection_artifact_inventory_mismatch')
    return json.loads((output / 'collection_report.json').read_text(encoding='utf-8'))


def reparse_publications(collection, output):
    """Validate dates from the freshly collected citations without overwriting raw.

    This is a derivative of the verified new network snapshot, not reuse of any
    pre-rebuild data. Preserve citation bytes, receipt dates and original hashes.
    """
    collection, output = Path(collection).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('fresh_date_validation_output_already_exists')
    if output.parent != collection.parent or output.name != 'faculty_dates':
        raise ValueError('date_validation_must_be_fresh_collection_sibling')
    verify_collection(collection)
    source_manifest_sha = _sha((collection / 'manifest.json').read_bytes())
    original_rows = [json.loads(line) for line in (collection / 'publications.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    rows, changes = [], []
    fields = ('publication_year', 'publication_month', 'publication_date', 'date_precision', 'date_evidence', 'date_status')
    for row in original_rows:
        dates = publication_date_evidence(row['title_text'])
        before = {key: row.get(key) for key in fields}
        if before != dates:
            changes.append({'publication_id': row['publication_id'], 'before': before, 'after': dates})
        rows.append({**row, **dates, 'date_validation_version': VERSION,
                     'source_collection_manifest_sha256': source_manifest_sha,
                     'source_publication_record_sha256': _sha(json.dumps(row, ensure_ascii=False, sort_keys=True).encode())})
    output.mkdir()
    report = {'schema_version': 'fresh-publication-date-validation/1.0', 'publication_count': len(rows),
              'changed_date_count': len(changes), 'changes': changes,
              'date_precision_counts': dict(Counter(row['date_precision'] for row in rows)),
              'source_collection_manifest_sha256': source_manifest_sha,
              'source_publications_sha256': _sha((collection / 'publications.jsonl').read_bytes()),
              'historical_training_ready': False,
              'scope': 'date_validation_of_verified_fresh_network_snapshot_no_refetch_no_old_data'}
    _jsonl(output / 'publications.jsonl', rows)
    _json(output / 'date_validation_report.json', report)
    _json(output / 'manifest.json', {'schema_version': report['schema_version'],
          'created_at': datetime.now(timezone.utc).isoformat(), 'source_collection': str(collection),
          'source_collection_manifest_sha256': source_manifest_sha, 'parser_sha256': _sha(Path(__file__).read_bytes()),
          'artifacts': {name: _sha((output / name).read_bytes()) for name in ('publications.jsonl', 'date_validation_report.json')}})
    verify_publication_dates(output)
    return report


def verify_publication_dates(output):
    output = Path(output).resolve()
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    collection = Path(manifest['source_collection']).resolve()
    verify_collection(collection)
    if _sha((collection / 'manifest.json').read_bytes()) != manifest['source_collection_manifest_sha256']:
        raise ValueError('fresh_collection_manifest_binding_mismatch')
    if set(manifest['artifacts']) != {'publications.jsonl', 'date_validation_report.json'}:
        raise ValueError('date_validation_artifact_inventory_mismatch')
    for name, expected in manifest['artifacts'].items():
        if _sha((output / name).read_bytes()) != expected:
            raise ValueError('date_validation_artifact_hash_mismatch')
    actual = {path.name for path in output.iterdir()}
    if actual != {'publications.jsonl', 'date_validation_report.json', 'manifest.json'}:
        raise ValueError('date_validation_artifact_inventory_mismatch')
    return json.loads((output / 'date_validation_report.json').read_text(encoding='utf-8'))


def collect_external_profiles(collection, output, *, delay=1.0, retries=2, fetcher=None):
    """Attempt only verified URL seeds publicly; blocked sources keep FIT fallback."""
    collection, output = Path(collection).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('fresh_external_output_already_exists')
    if output.parent != collection.parent or output.name != 'faculty_external':
        raise ValueError('external_must_be_fresh_collection_sibling')
    verify_collection(collection)
    if collection.parts[-4:-1] != ('data_rebuild', 'nested_rl_20261028', collection.parent.name) or collection.name != 'faculty':
        raise ValueError('new_nested_namespace_required')
    output.mkdir()
    (output / 'raw').mkdir()
    receipts, profiles, publications = [], [], []
    robots_cache = {}
    last_request = 0.0

    class PublicRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            before, after = urlsplit(req.full_url), urlsplit(newurl)
            if after.scheme != 'https' or after.hostname != before.hostname:
                raise ValueError('external_redirect_outside_source_host')
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    def live(url):
        try:
            response = build_opener(PublicRedirects()).open(Request(url, headers={
                'User-Agent': USER_AGENT, 'Cache-Control': 'no-cache'}), timeout=25)
        except HTTPError as exc:
            response = exc
        with response:
            return response.read(MAX_BYTES + 1), response.code, response.url

    def get(url, kind):
        nonlocal last_request
        for attempt in range(retries + 1):
            time.sleep(max(0, delay - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            row = {'url': url, 'kind': kind, 'attempt': attempt + 1, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                   'retrieval': 'fresh_network', 'http_status': None, 'status': 'failed', 'error': None}
            try:
                body, code, final_url = (fetcher or live)(url)
                if len(body) > MAX_BYTES:
                    raise ValueError('source_response_size_limit')
                if urlsplit(final_url).hostname != urlsplit(url).hostname:
                    raise ValueError('external_redirect_host_mismatch')
                sha = _sha(body)
                path = output / 'raw' / (sha + '.html')
                path.write_bytes(body)
                row.update(http_status=code, final_url=final_url, sha256=sha,
                           raw_path=path.relative_to(output).as_posix(), size_bytes=len(body),
                           status='fetched' if code == 200 else 'http_error')
                receipts.append(row)
                if code < 500 and code != 429:
                    return body, row
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
                receipts.append(row)
        return b'', row

    faculty = [json.loads(line) for line in (collection / 'faculty.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    for person in faculty:
        for platform, account in person.get('external_profiles', {}).items():
            url = account.get('url')
            if not url or _external_platform(url) != platform:
                continue
            parsed = urlsplit(url)
            origin = f'{parsed.scheme}://{parsed.netloc}'
            if origin not in robots_cache:
                body, receipt = get(origin + '/robots.txt', 'robots')
                robot = RobotFileParser(origin + '/robots.txt')
                robot.parse(body.decode('utf-8', errors='replace').splitlines() if receipt['http_status'] == 200 else
                            ['User-agent: *', 'Allow: /' if receipt['http_status'] == 404 else 'Disallow: /'])
                robots_cache[origin] = robot
            profile = {'advisor_id': person.get('advisor_id'), 'platform': platform, 'url': url,
                       'identity_basis': account.get('identity_basis'), 'status': 'robots_disallowed',
                       'fallback': 'official_fit_only', 'publication_count': 0}
            if robots_cache[origin].can_fetch(USER_AGENT, url):
                body, receipt = get(url, 'external_profile')
                profile.update(source_sha256=receipt.get('sha256'), retrieved_at=receipt['retrieved_at'],
                               http_status=receipt['http_status'], status='http_error')
                if receipt['http_status'] == 200:
                    soup = BeautifulSoup(body, 'html.parser')
                    blocked = re.search(r'captcha|unusual traffic|access denied|verify you are human', soup.get_text(' ', strip=True), re.I)
                    profile['status'] = 'challenge' if blocked else 'unsupported_public_markup'
                    items = soup.select('tr.gsc_a_tr') if platform == 'google_scholar' and not blocked else []
                    if items:
                        profile['status'] = 'collected'
                    for index, item in enumerate(items):
                        title, year_node = item.select_one('.gsc_a_at'), item.select_one('.gsc_a_y')
                        if not title or not title.get_text(' ', strip=True):
                            continue
                        year_text = year_node.get_text(' ', strip=True) if year_node else ''
                        dates = publication_date_evidence(year_text) if re.fullmatch(r'(19|20)\d{2}', year_text) else publication_date_evidence('')
                        publications.append({'publication_id': 'ext_' + _sha((url + str(index)).encode())[:24],
                            'advisor_id': person.get('advisor_id'), 'platform': platform, 'identity_basis': account.get('identity_basis'),
                            'title_text': title.get_text(' ', strip=True), 'original_snippet': str(item),
                            'locator': f'tr.gsc_a_tr[{index}]', 'source_url': url, 'source_sha256': receipt['sha256'],
                            'retrieved_at': receipt['retrieved_at'], 'historical_feature_available_at': None,
                            'links': [urljoin(url, title['href'])] if title.get('href') else [], **dates})
                        profile['publication_count'] += 1
            profiles.append(profile)
    report = {'schema_version': 'fresh-external-faculty/1.0', 'profile_count': len(profiles),
              'publication_count': len(publications), 'status_counts': dict(Counter(p['status'] for p in profiles)),
              'http_receipt_count': len(receipts), 'historical_training_ready': False,
              'identity_review_required': any(p['identity_basis'] == 'owner_url_seed_only' for p in profiles),
              'scope': 'public_seed_urls_only_no_auth_no_captcha_bypass_no_pagination'}
    _jsonl(output / 'profiles.jsonl', profiles)
    _jsonl(output / 'publications.jsonl', publications)
    _jsonl(output / 'sources.jsonl', receipts)
    _json(output / 'collection_report.json', report)
    _json(output / 'manifest.json', {'schema_version': report['schema_version'], 'source_collection': str(collection),
        'source_collection_manifest_sha256': _sha((collection / 'manifest.json').read_bytes()),
        'collector_sha256': _sha(Path(__file__).read_bytes()), 'created_at': datetime.now(timezone.utc).isoformat(),
        'artifacts': {p.relative_to(output).as_posix(): _sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}})
    return report
