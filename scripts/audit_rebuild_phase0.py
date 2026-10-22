"""Read-only source inventory. Private outputs belong outside Git; no entity extraction."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pymupdf


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


SOURCE_FORMATS = {'pdf', 'docx', 'rar'}


def inventory(root: Path, cached_pdf_rows: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    rows, entries = [], []
    cache = {r['relative_path']: r for r in (cached_pdf_rows or []) if r.get('status') == 'parsed'}
    # Do not follow symlinks to unrelated data. Include them as explicit errors.
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            hidden = any(p.startswith('.') for p in Path(relative).parts) or bool(getattr(info, 'st_file_attributes', 0) & 2)
            entry = dict(relative_path=relative, kind='directory' if path.is_dir() else 'file',
                         hidden=hidden, symlink=path.is_symlink(), size_bytes=info.st_size,
                         format=path.suffix.lower().lstrip('.'), sha256='', exclusion_reason='')
            entries.append(entry)
            if path.is_dir():
                continue
            if path.suffix.lower() == '.ini':
                entry.update(sha256=sha256(path), exclusion_reason='system_metadata_ini')
                continue
            row = dict(relative_path=relative, size_bytes=info.st_size, hidden=hidden,
                       format=entry['format'], sha256='', page_count=None, text_length=None, encrypted=False,
                       low_text_pages=None, scan_candidate=None, status='failed', parse_error='', pdf_inspection='not_applicable',
                       parser_version=pymupdf.VersionBind if entry['format'] == 'pdf' else '')
            try:
                if path.is_symlink():
                    raise ValueError('symlink_source_not_allowed')
                row['sha256'] = sha256(path)
                entry['sha256'] = row['sha256']
                if row['format'] != 'pdf':
                    row['status'] = 'inventoried' if row['format'] in SOURCE_FORMATS else 'unsupported'
                    rows.append(row)
                    continue
                cached = cache.get(relative)
                if (cached and cached.get('sha256') == row['sha256'] and cached.get('page_count')
                        and cached.get('parser_version') == pymupdf.VersionBind):
                    for field in ('page_count', 'text_length', 'encrypted', 'low_text_pages', 'scan_candidate'):
                        value = cached[field]
                        if isinstance(value, str):
                            value = value == 'True' if field in {'encrypted', 'scan_candidate'} else int(value)
                        row[field] = value
                    row.update(status='parsed', pdf_inspection='cached_sha256_verified')
                    rows.append(row)
                    continue
                row['pdf_inspection'] = 'PyMuPDF_embedded_text'
                with pymupdf.open(path) as doc:
                    if not doc.is_pdf:
                        raise ValueError('not_pdf_content')
                    row['encrypted'] = bool(doc.is_encrypted or doc.metadata.get('encryption'))
                    row['page_count'] = doc.page_count
                    if doc.needs_pass:
                        row.update(status='encrypted', parse_error='password_required')
                    else:
                        lengths = [len(page.get_text().strip()) for page in doc]
                        row.update(text_length=sum(lengths), low_text_pages=sum(n < 50 for n in lengths),
                                   scan_candidate=any(n < 50 for n in lengths), status='parsed')
                        if not lengths:
                            raise ValueError('zero_pages')
                if path.stat().st_size != info.st_size or sha256(path) != row['sha256']:
                    raise ValueError('source_changed_during_inventory')
            except Exception as exc:
                # Detailed parser messages can contain source text; keep only error class.
                row.update(status='failed', parse_error=type(exc).__name__)
            rows.append(row)
    return sorted(rows, key=lambda r: r['relative_path']), sorted(entries, key=lambda r: r['relative_path'])


def quality(rows: list[dict], expected: int = 220) -> dict:
    groups = defaultdict(list)
    for row in rows:
        if row['sha256']:
            groups[row['sha256']].append(row['relative_path'])
    invalid = [r['relative_path'] for r in rows if r['status'] not in {'parsed', 'inventoried'}]
    return dict(status='verified' if len(rows) == expected and not invalid else 'blocked',
                scope='Original source inventory gate; extraction completeness belongs to Phase 1',
                expected_count=expected, actual_count=len(rows), count_delta=len(rows) - expected,
                format_counts=dict(Counter(r['format'] for r in rows)),
                invalid_files=invalid, duplicate_hash_groups=[v for v in groups.values() if len(v) > 1],
                page_count=sum(r['page_count'] or 0 for r in rows),
                low_text_pages=sum(r['low_text_pages'] or 0 for r in rows),
                scanned_flag_definition='Candidate only: at least one page has <50 stripped text characters; blank pages also qualify.',
                unique_student_count=None)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/1.pdfs'))
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output == source or source in output.parents or output in source.parents:
        parser.error('Source and output must be disjoint')
    for directory in ('raw_index', 'bronze', 'silver', 'gold', 'reports'):
        (output / directory).mkdir(parents=True, exist_ok=True)
    reports = output / 'reports'
    cached_rows = []
    previous = reports / 'input_inventory.csv'
    if previous.exists():
        previous_quality = reports / 'input_quality.json'
        if previous_quality.exists():
            metadata = json.loads(previous_quality.read_text(encoding='utf-8'))
            if metadata.get('inventory_sha256') == sha256(previous) and metadata.get('parser_version') == pymupdf.VersionBind:
                with previous.open(encoding='utf-8-sig', newline='') as stream:
                    cached_rows = list(csv.DictReader(stream))
                for row in cached_rows:
                    # Earlier inventory format stored parser version at report level.
                    row.setdefault('parser_version', metadata['parser_version'])
        history = reports / 'history' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        history.mkdir(parents=True, exist_ok=False)
        for path in reports.iterdir():
            if path.is_file():
                shutil.copy2(path, history / path.name)
    rows, entries = inventory(source, cached_pdf_rows=cached_rows)
    report = quality(rows)
    report['excluded_files'] = [r for r in entries if r['exclusion_reason']]
    report.update(retrieved_at=datetime.now(timezone.utc).isoformat(), parser='PyMuPDF', parser_version=pymupdf.VersionBind)
    write_csv(output / 'reports/input_inventory.csv', rows, list(rows[0]) if rows else ['relative_path'])
    write_csv(output / 'reports/all_source_entries.csv', entries, list(entries[0]) if entries else ['relative_path'])
    write_csv(output / 'reports/non_pdf_entries.csv', [r for r in entries if r['kind'] != 'file' or Path(r['relative_path']).suffix.lower() != '.pdf'], list(entries[0]) if entries else ['relative_path'])
    report['inventory_sha256'] = sha256(output / 'reports/input_inventory.csv')
    (output / 'reports/input_quality.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    # Exact path lists remain in the private reports, never standard output.
    print(json.dumps({k: report[k] for k in ('status', 'expected_count', 'actual_count', 'count_delta', 'page_count', 'low_text_pages')}))
    return 0 if report['status'] == 'verified' else 2


if __name__ == '__main__':
    raise SystemExit(main())
