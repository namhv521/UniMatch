"""Fresh full-document extraction into a new private namespace, no old artifacts.

Raw originals are read and copied anew, exact-byte aliases remain explicit, and
all extracted student/supervisor/date fields are candidates requiring review.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import unicodedata

from .document_sources import extract_docx
from .pdf_extract import iter_pdf_blocks
from .semester_evidence import term_evidence
from .semester_versions import classify_version
from .student_candidates import extract_candidates, validate_evidence


SCHEMA_VERSION = 'fresh-students/1.0'
DATE_CONTEXT = re.compile(r'(?:hà\s*nội|ha\s*noi|hanoi|thời\s*gian\s*(?:bảo\s*vệ|hoàn\s*thành)|ngày\s*bảo\s*vệ)', re.I)
SUPERVISOR = re.compile(r'(?:giảng\s*viên|giáo\s*viên|người|cán\s*bộ)\s*hướng\s*dẫn|\bGVHD\b', re.I)


def _digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def _line(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')


def _reference(block, snippet):
    keys = ('source_id', 'source_file', 'source_sha256', 'block_id', 'locator', 'page',
            'extraction_method', 'parser_version', 'archive_chain')
    return {**{k: block[k] for k in keys if k in block}, 'snippet': snippet}


def _quoted_cover_title(blocks):
    """Recover a quoted cover header without changing original evidence offsets."""
    front = [b for b in blocks if b.get('page') in (1, 2) and b.get('kind', 'block') == 'block'][:160]
    text, spans = '', []
    for block in front:
        start = len(text)
        text += block['text'] + '\n'
        spans.append((start, len(text) - 1, block))
    match = re.search(r'[“"«](?:khóa|khoá)\s+luận\s+tốt\s+nghiệp[”"»]\s*\n+(.*?)\n\s*[“"]?(?:tên\s+sinh\s+viên|họ\s+và\s+tên|sinh\s+viên\s+thực\s+hiện)', text, re.I | re.S)
    if not match:
        return None
    value = ' '.join(unicodedata.normalize('NFC', match[1]).split())
    if not 8 <= len(value) <= 800:
        return None
    start, end = match.span(1)
    evidence = []
    for left, right, block in spans:
        if start < right and end > left:
            snippet = block['text'][max(0, start-left):min(right, end)-left]
            if snippet.strip():
                evidence.append(_reference(block, snippet))
    return {'value': value, 'evidence_type': 'observed_quoted_cover_title_candidate',
            'confidence': None, 'evidence': evidence}


def cover_metadata(blocks):
    """Locate date/supervision evidence only on the cover/front matter.

    Cities/dates require an explicit cover context. Bibliography years never set
    the thesis year. Ambiguous/conflicting evidence stays unresolved.
    """
    front = [b for b in blocks if b.get('kind', 'block') == 'block' and b.get('page', 1) <= 3][:160]
    lines = [(line.strip(), b) for b in front for line in b['text'].splitlines() if line.strip()]
    supervisors, dates = [], []
    for i, (line, block) in enumerate(lines):
        marker = SUPERVISOR.search(line)
        if marker:
            value = line[marker.end():].strip(' :：-')
            quote = line
            evidence = [_reference(block, line)]
            if not value and i + 1 < len(lines):
                value, next_block = lines[i + 1]
                evidence.append(_reference(next_block, value))
                quote += '\n' + value
            if value and not re.search(r'(?:mã\s*sinh\s*viên|mssv|hà\s*nội|ngày|tháng)\b', value, re.I):
                item = {'value': value, 'evidence_type': 'observed_supervisor_label_candidate',
                        'review_status': 'pending', 'evidence': evidence, 'quote': quote}
                if not any(r['value'] == value for r in supervisors):
                    supervisors.append(item)
        if block.get('page') not in (1, 2) or not DATE_CONTEXT.search(unicodedata.normalize('NFC', line)):
            continue
        context = line
        refs = [_reference(block, line)]
        # Many covers split "Hà Nội" and "tháng ... năm ..." into two blocks.
        if not re.search(r'\b(?:19|20)\d{2}\b', context) and i + 1 < len(lines) and lines[i + 1][1].get('page') in (1, 2):
            next_line, next_block = lines[i + 1]
            context += ' ' + next_line
            refs.append(_reference(next_block, next_line))
        parsed_context = unicodedata.normalize('NFC', context)
        full = re.search(r'ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*((?:19|20)\d{2})', parsed_context, re.I)
        month = re.search(r'tháng\s*(\d{1,2})\s*(?:(?:năm|[/.-])\s*)?((?:19|20)\d{2})', parsed_context, re.I)
        numeric = re.search(r'(?<!\d)(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*((?:19|20)\d{2})(?!\d)', parsed_context)
        short_month = re.search(r'(?:hà\s*nội|ha\s*noi|hanoi)\s*[,\-–:]?\s*(\d{1,2})\s*[/.-]\s*((?:19|20)\d{2})(?!\d)', parsed_context, re.I)
        value = None
        if full or numeric:
            match = full or numeric
            value = f'{match[3]}-{int(match[2]):02d}-{int(match[1]):02d}'
        elif month or short_month:
            match = month or short_month
            value = f'{match[2]}-{int(match[1]):02d}'
        else:
            years = set(re.findall(r'\b(?:19|20)\d{2}\b', parsed_context))
            if len(years) == 1:
                value = int(next(iter(years)))
        if value is not None:
            try:
                classification = classify_version(value)
            except (ValueError, TypeError):
                classification = {**classify_version(), 'status': 'invalid_source_date'}
            dates.append({'value': value, 'classification': classification, 'evidence': refs,
                          'review_status': 'pending', 'quote': context})
    classified = [r['classification'] for r in dates]
    valid = [r for r in classified if r.get('event_interval_lower_bound')]
    compatible = valid and len(valid) == len(classified) and max(r['event_interval_lower_bound'] for r in valid) <= min(r['event_interval_upper_bound'] for r in valid)
    if compatible:
        precision_rank = {'year': 0, 'month': 1, 'day': 2, 'timestamp': 3}
        temporal = max(valid, key=lambda r: precision_rank.get(r.get('precision'), -1))
    elif len(dates) == 1:
        temporal = classified[0]
    elif dates:
        temporal = {**classify_version(), 'status': 'ambiguous',
                    'possible_versions': sorted({v for r in classified for v in r['possible_versions']}),
                    'event_interval_lower_bound': min((r['event_interval_lower_bound'] for r in valid), default=None),
                    'event_interval_upper_bound': max((r['event_interval_upper_bound'] for r in valid), default=None),
                    'reason': 'conflicting_or_incomplete_cover_dates'}
    else:
        temporal = classify_version()
    return {'supervisor_names': supervisors, 'date_evidence': dates, 'temporal': temporal,
            'academic_term_evidence': term_evidence('\n'.join(line for line, _ in lines)),
            'feature_available_at': None, 'historical_training_eligible': False}


def verify_collection(output):
    output = Path(output).resolve()
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('source_collection'):
        parent = Path(manifest['source_collection']).resolve()
        if parent.parent != output.parent or parent == output:
            raise ValueError('invalid_source_collection')
        verify_collection(parent)
        if _digest(parent / 'manifest.json') != manifest['source_collection_manifest_sha256']:
            raise ValueError('source_collection_manifest_mismatch')
        for name, sha in manifest.get('source_input_sha256', {}).items():
            if _digest(parent / name) != sha:
                raise ValueError('source_collection_input_mismatch')
    artifacts = manifest['artifacts']
    for name, sha in artifacts.items():
        path = (output / name).resolve()
        if not path.is_relative_to(output) or not path.is_file() or _digest(path) != sha:
            raise ValueError(f'collection_artifact_hash_mismatch:{name}')
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    if actual != set(artifacts):
        raise ValueError('collection_inventory_mismatch')
    return manifest['report']


def collect_students(source, output, *, ocr='off', tessdata=None):
    """Snapshot and freshly parse all current sources without reading old gold.

    Default OCR-off deliberately records scan pages for review instead of claiming
    they were extracted. Pass auto and existing tessdata explicitly to enable it.
    Archives/unsupported types remain copied and inventoried as pending.
    """
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('source_output_overlap')
    if output.exists():
        raise FileExistsError('fresh_output_required')
    if not source.is_dir():
        raise ValueError('source_directory_required')
    if ocr not in ('off', 'auto'):
        raise ValueError('ocr_must_be_off_or_auto')
    # Check inventory before creating any output; source copies are never reused.
    paths = sorted(p for p in source.rglob('*') if p.is_file())
    excluded = [p for p in paths if p.suffix.lower() == '.ini']
    paths = [p for p in paths if p.suffix.lower() != '.ini']
    if any(p.is_symlink() or not p.resolve().is_relative_to(source) for p in paths):
        raise ValueError('source_symlinks_or_escape_forbidden')
    output.mkdir(parents=True)
    (output / 'raw').mkdir()
    captured = datetime.now(timezone.utc).isoformat()
    aliases = defaultdict(list)
    for path in paths:
        aliases[_digest(path)].append(path)
    counts, versions, formats = Counter(), Counter(), Counter()
    total_candidates, block_count, evidence_errors, ocr_candidates = 0, 0, 0, 0
    streams = {name: (output / (name + '.jsonl')).open('w', encoding='utf-8')
               for name in ('students', 'documents', 'sources', 'blocks', 'page_outcomes')}
    try:
        for content_sha, group in aliases.items():
            original = group[0]
            suffix = original.suffix.lower()
            relative = original.relative_to(source).as_posix()
            raw_relative = 'raw/' + content_sha + suffix
            raw = output / raw_relative
            shutil.copyfile(original, raw)
            if _digest(raw) != content_sha or any(_digest(p) != content_sha for p in group):
                raise ValueError('source_changed_during_snapshot')
            source_id = 'doc_' + content_sha
            names = [p.relative_to(source).as_posix() for p in group]
            ref = {'source_id': source_id, 'source_file': relative, 'source_sha256': content_sha,
                   'archive_chain': [], 'captured_at': captured, 'collection_method': 'fresh_local_raw_copy'}
            for path, name in zip(group, names):
                formats[path.suffix.lower().lstrip('.')] += 1
                _line(streams['sources'], {**ref, 'source_file': name, 'original_path': str(path),
                      'source_aliases': names, 'raw_path': raw_relative, 'size_bytes': path.stat().st_size})
            blocks, outcomes, reason = [], [], ''
            try:
                if suffix == '.pdf':
                    for item in iter_pdf_blocks(raw, ref, ocr_mode=ocr, tessdata=tessdata):
                        if item['kind'] == 'block':
                            blocks.append(item)
                            _line(streams['blocks'], item)
                            block_count += 1
                        else:
                            outcomes.append(item)
                            _line(streams['page_outcomes'], item)
                            counts['page_' + item['status']] += 1
                            ocr_candidates += int(item.get('ocr_candidate', False))
                    if not blocks:
                        reason = 'no_readable_blocks'
                elif suffix == '.docx':
                    blocks = extract_docx(raw, ref)
                    for item in blocks:
                        _line(streams['blocks'], item)
                        block_count += 1
                    if not blocks:
                        reason = 'no_readable_blocks'
                else:
                    reason = 'archive_expansion_pending' if suffix in ('.rar', '.zip') else 'unsupported_format_pending'
            except Exception as exc:
                reason = f'{type(exc).__name__}:{exc}'
            metadata = cover_metadata(blocks)
            candidates = extract_candidates(blocks)
            errors = validate_evidence(candidates, blocks)
            evidence_errors += len(errors)
            for candidate in candidates:
                row = {**candidate, **metadata, 'schema_version': SCHEMA_VERSION, 'source_aliases': names,
                       'raw_path': raw_relative, 'captured_at': captured, 'review_status': 'needs_review',
                       'provenance_validation': 'passed' if not errors else 'failed',
                       'preferences': None, 'observed_outcomes': None}
                _line(streams['students'], row)
                total_candidates += 1
                versions[row['temporal'].get('version') or row['temporal']['status']] += 1
            has_page_problem = any(o['status'] in ('failed', 'quarantined') for o in outcomes)
            status = 'failed_or_pending' if reason or errors else ('partial' if has_page_problem else 'extracted')
            counts['document_' + status] += 1
            _line(streams['documents'], {**ref, 'schema_version': SCHEMA_VERSION,
                  'source_aliases': names, 'raw_path': raw_relative, 'format': suffix.lstrip('.'),
                  'status': status, 'reason': reason, 'block_count': len(blocks),
                  'page_outcome_count': len(outcomes), 'candidate_ids': [c['candidate_id'] for c in candidates],
                  'evidence_errors': errors, **metadata})
            print(f'FRESH_STUDENTS {len(group)} alias(es) {relative}: {status}, {len(blocks)} blocks', flush=True)
    finally:
        for stream in streams.values():
            stream.close()
    report = {'schema_version': SCHEMA_VERSION, 'scope': 'fresh_full_document_candidate_extraction',
              'source_root': str(source), 'captured_at': captured, 'source_files': len(paths),
              'unique_content': len(aliases), 'duplicate_aliases': len(paths) - len(aliases),
              'system_files_excluded': len(excluded), 'source_formats': dict(formats),
              'student_candidates': total_candidates, 'blocks': block_count, 'counts': dict(counts),
              'failed_or_pending_documents': counts['document_failed_or_pending'],
              'evidence_errors': evidence_errors, 'version_candidate_counts': dict(versions),
              'ocr_mode': ocr, 'ocr_candidate_pages': ocr_candidates, 'training_ready': False,
              'limitations': ['All student/supervisor/date fields require review; no academic approvals inferred.',
                             'Thesis-final technologies do not prove pre-allocation student mastery.',
                             'Event dates are separate from unknown prediction-time feature availability.',
                             'No old gold/bronze/features were read. Archives/unsupported documents stay pending.',
                             'OCR-disabled or unavailable scan pages remain explicit in page_outcomes.jsonl.']}
    _json(output / 'report.json', report)
    artifacts = {p.relative_to(output).as_posix(): _digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    _json(output / 'manifest.json', {'schema_version': SCHEMA_VERSION, 'report': report,
          'code_sha256': {str(p.relative_to(Path(__file__).parents[2])): _digest(p) for p in
                         (Path(__file__), Path(__file__).with_name('semester_versions.py'),
                          Path(__file__).with_name('pdf_extract.py'), Path(__file__).with_name('document_sources.py'),
                          Path(__file__).with_name('student_candidates.py'))}, 'artifacts': artifacts})
    verify_collection(output)
    return report


def rederive_temporal(source_collection, output):
    """Derive cover-pages-only metadata from this fresh snapshot; retain original bytes."""
    source, output = Path(source_collection).resolve(), Path(output).resolve()
    original_report = verify_collection(source)
    if output.exists():
        raise FileExistsError('fresh_output_required')
    if output.parent != source.parent:
        raise ValueError('sibling_derivative_required')
    front = defaultdict(list)
    with (source / 'blocks.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            block = json.loads(line)
            key = block['source_id']
            if block.get('page', 1) <= 3 and len(front[key]) < 160:
                front[key].append(block)
    metadata = {key: cover_metadata(blocks) for key, blocks in front.items()}
    titles = {key: _quoted_cover_title(blocks) for key, blocks in front.items()}
    title_fixes = 0
    output.mkdir()
    versions, cohorts = Counter(), Counter()
    count = 0
    with (source / 'students.jsonl').open(encoding='utf-8') as incoming, (output / 'students.jsonl').open('w', encoding='utf-8') as outgoing:
        for line in incoming:
            row = json.loads(line)
            row.update(metadata.get(row['source_id'], cover_metadata([])))
            if not row['fields'].get('thesis_title') and titles.get(row['source_id']):
                row['fields']['thesis_title'] = titles[row['source_id']]
                row['review_reasons'] = [reason for reason in row['review_reasons'] if reason != 'missing_thesis_title']
                row['review_reasons'].append('quoted_cover_title_requires_review')
                title_fixes += 1
            row['source_collection'] = str(source)
            row['temporal_derivation'] = 'cover_pages_1_2_seasons_jan_may_jun_aug_sep_dec'
            _line(outgoing, row)
            count += 1
            temporal = row['temporal']
            versions[temporal.get('version') or temporal['status']] += 1
            cohorts[temporal.get('academic_cohort') or 'unresolved'] += 1
    report = {'scope': 'fresh_snapshot_cover_temporal_derivative', 'student_candidates': count,
              'quoted_title_candidates_recovered': title_fixes,
              'version_candidate_counts': dict(versions), 'academic_cohort_counts': dict(cohorts),
              'original_version_candidate_counts': original_report['version_candidate_counts'],
              'training_ready': False, 'date_source_pages': [1, 2],
              'limitations': ['DOCX has no rendered page numbers; cover cohort remains pending.',
                             'Feature availability and preferences remain unknown.',
                             'June-August is summer; summer 2024.3 joins V3, not V2.']}
    _json(output / 'report.json', report)
    _json(output / 'manifest.json', {'schema_version': SCHEMA_VERSION, 'report': report,
          'source_collection': str(source), 'source_collection_manifest_sha256': _digest(source / 'manifest.json'),
          'source_input_sha256': {name: _digest(source / name) for name in ('students.jsonl', 'blocks.jsonl')},
          'code_sha256': {p.name: _digest(p) for p in (Path(__file__), Path(__file__).with_name('semester_versions.py'))},
          'artifacts': {name: _digest(output / name) for name in ('students.jsonl', 'report.json')}})
    verify_collection(output)
    return report
