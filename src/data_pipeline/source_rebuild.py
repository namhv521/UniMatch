"""Phase 1 orchestration with immutable runs and source/evidence conservation."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .document_sources import expand_archive, extract_docx
from .pdf_extract import iter_pdf_blocks
from .student_candidates import clean, extract_candidates, validate_evidence


def _code_hashes():
    # Freeze the modules that actually execute Phase 1, not unrelated later phases.
    names = ('document_sources.py', 'pdf_extract.py', 'student_candidates.py', 'source_rebuild.py')
    return {name: digest(Path(__file__).parent / name) for name in names}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def _csv(path, rows, empty_fields=('source_id', 'status', 'reason')):
    keys = list(dict.fromkeys(key for row in rows for key in row)) or list(empty_fields)
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def rebuild(source: Path, output: Path, *, ocr_mode='auto', max_depth=3) -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('source_output_overlap')
    previous_gate = json.loads((output / 'reports/phase0_gate.json').read_text(encoding='utf-8'))
    if previous_gate.get('status') != 'verified' or not previous_gate.get('can_start_phase1'):
        raise ValueError('phase0_not_verified')
    inventory_path = output / 'reports/input_inventory.csv'
    inventory_hash = digest(inventory_path)
    if inventory_hash != previous_gate.get('inventory_sha256'):
        raise ValueError('phase0_inventory_checksum_mismatch')
    with inventory_path.open(encoding='utf-8-sig', newline='') as stream:
        originals = list(csv.DictReader(stream))
    paths = [row['relative_path'] for row in originals]
    if (not originals or len(originals) != previous_gate.get('actual_source_files')
            or len(set(paths)) != len(paths)):
        raise ValueError('phase0_inventory_count_or_identity_mismatch')
    code_hashes = _code_hashes()
    # Check inputs before writing any derived documents.
    for row in originals:
        path = (source / row['relative_path']).resolve()
        if source not in path.parents or path.is_symlink():
            raise ValueError('unsafe_source_path')
        if digest(path) != row['sha256']:
            raise ValueError('source_hash_mismatch')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run = output / 'phase1_runs' / run_id
    for name in ('bronze', 'reports', 'derived'):
        (run / name).mkdir(parents=True, exist_ok=False)
    sources, members, candidates, outcomes, review, evidence_errors = [], [], [], [], [], []
    block_ids = set()
    expected_pages = {r['relative_path']: int(r['page_count']) for r in originals if r.get('page_count')}
    original_ids, total_expanded_bytes = set(), 0
    streams = {name: (run / f'bronze/{name}.jsonl').open('w', encoding='utf-8')
               for name in ('pdf_pages', 'document_blocks', 'page_outcomes')}

    def write(name, row):
        if name == 'document_blocks':
            if row['block_id'] in block_ids:
                evidence_errors.append({'source_id': row['source_id'], 'reason': 'duplicate_block_id'})
            block_ids.add(row['block_id'])
        streams[name].write(json.dumps(row, ensure_ascii=False) + '\n')

    def process(path, relative, expected_hash, chain, depth, original):
        nonlocal total_expanded_bytes
        source_id = hashlib.sha256((relative + '\0' + expected_hash).encode()).hexdigest()
        ref = {'source_id': source_id, 'source_file': relative, 'source_sha256': expected_hash, 'archive_chain': chain}
        if original:
            original_ids.add(source_id)
        row = {**ref, 'format': path.suffix.lower().lstrip('.'), 'original': original,
               'status': 'failed', 'reason': '', 'block_count': 0, 'candidate_ids': []}
        sources.append(row)
        try:
            if digest(path) != expected_hash:
                raise ValueError('source_hash_mismatch')
            if path.suffix.lower() in {'.rar', '.zip'}:
                if depth >= max_depth or total_expanded_bytes >= 2 * 1024**3 or len(sources) > 2000:
                    row.update(status='quarantined', reason='whole_run_archive_budget')
                    return
                archive_rows = expand_archive(path, run / 'derived' / source_id,
                                              max_total_bytes=2 * 1024**3-total_expanded_bytes,
                                              max_members=max(0, 10000-len(members)))
                for member in archive_rows:
                    item = {**member, 'parent_source_id': source_id, 'parent_source_file': relative, 'archive_chain': chain}
                    members.append(item)
                    if member['status'] != 'extracted':
                        if member['status'] not in {'directory'}:
                            review.append({'source_id': source_id, 'member_path': member['member_path'], 'reason': member['reason']})
                        continue
                    total_expanded_bytes += member['size_bytes']
                    # Reserve one source record for every original still to process.
                    if len(sources) - len(original_ids) >= 2000 - len(originals):
                        item.update(status='quarantined', reason='whole_run_source_count_limit')
                        review.append({'source_id': source_id, 'member_path': member['member_path'], 'reason': item['reason']})
                        continue
                    derived = Path(member['extracted_path'])
                    parent = {'source_file': relative, 'sha256': expected_hash, 'member_path': member['member_path'],
                              'member_sha256': member['member_sha256'], 'parser': member['parser'], 'parser_version': member['parser_version']}
                    process(derived, relative + '!' + member['member_path'], member['member_sha256'], chain + [parent], depth+1, False)
                issues = [m for m in archive_rows if m['status'] in {'failed', 'quarantined'}]
                row.update(status='quarantined' if issues else 'extracted', reason='archive_members_require_review' if issues else '')
                row['member_count'] = len(archive_rows)
                return
            blocks, page_rows = [], []
            if path.suffix.lower() == '.pdf':
                for item in iter_pdf_blocks(path, ref, ocr_mode=ocr_mode, tessdata=output / 'tools/tessdata'):
                    if item['kind'] == 'block':
                        blocks.append(item)
                        write('pdf_pages', item)
                        write('document_blocks', item)
                    else:
                        page_rows.append(item)
                        write('page_outcomes', item)
                        outcomes.append({k: v for k, v in item.items() if k != 'archive_chain'})
                if relative in expected_pages:
                    observed = [p['page'] for p in page_rows if p['page'] is not None]
                    row['expected_pages'] = expected_pages[relative]
                    if (not any(p['page'] is None for p in page_rows)
                            and sorted(observed) != list(range(1, expected_pages[relative]+1))):
                        evidence_errors.append({'source_id': source_id, 'reason': 'page_conservation_failure'})
            elif path.suffix.lower() == '.docx':
                blocks = extract_docx(path, ref)
                for item in blocks:
                    write('document_blocks', item)
            else:
                row.update(status='quarantined', reason='unsupported_document_format')
                return
            found = extract_candidates(blocks)
            errors = validate_evidence(found, blocks)
            evidence_errors.extend(errors)
            for candidate in found:
                if any(p['status'] in {'failed', 'quarantined'} for p in page_rows):
                    candidate['review_reasons'].append('incomplete_page_extraction')
                    candidate['status'] = 'quarantined'
                if errors:
                    candidate['review_reasons'].append('invalid_source_evidence')
                    candidate['status'] = 'quarantined'
            candidates.extend(found)
            row.update(block_count=len(blocks), candidate_ids=[c['candidate_id'] for c in found],
                       page_count=len(page_rows) if page_rows else None,
                       status='extracted' if found and all(c['status'] == 'extracted' for c in found) else 'quarantined',
                       reason='' if found else 'no_candidate_text')
            if any(p['status'] == 'failed' for p in page_rows) and not blocks:
                row.update(status='failed', reason='document_extraction_failed')
            if digest(path) != expected_hash:
                row.update(status='failed', reason='source_changed_during_extraction')
        except Exception as exc:
            row.update(status='failed', reason=type(exc).__name__ + (':' + str(exc) if isinstance(exc, ValueError) else ''))
        finally:
            if row['status'] != 'extracted':
                review.append({'source_id': source_id, 'reason': row['reason'] or 'candidate_requires_review'})

    try:
        for number, original in enumerate(originals, 1):
            process(source / original['relative_path'], original['relative_path'], original['sha256'], [], 0, True)
            if number % 10 == 0:
                print(json.dumps({'phase': 1, 'original_sources_processed': number, 'total': len(originals)}), flush=True)
    finally:
        for stream in streams.values():
            stream.close()

    identities = defaultdict(list)
    hashes = defaultdict(list)
    for candidate in candidates:
        identifier = candidate['fields'].get('student_id', {}).get('value')
        if identifier:
            identities[identifier].append(candidate)
        hashes[candidate['source_sha256']].append(candidate)
    for group in list(identities.values()) + list(hashes.values()):
        if len(group) > 1:
            for candidate in group:
                candidate['review_reasons'] = sorted(set(candidate['review_reasons'] + ['duplicate_identity_or_source']))
                candidate['status'] = 'quarantined'
    # Title similarity is a review hint only; no entity merge and no student exclusion.
    titled = [(c, clean(c['fields']['thesis_title']['value']).casefold()) for c in candidates if 'thesis_title' in c['fields']]
    near_duplicates = []
    for i, (left, title) in enumerate(titled):
        for right, other in titled[i+1:]:
            similarity = SequenceMatcher(None, title, other).ratio()
            if similarity >= 0.94:
                near_duplicates.append({'left': left['candidate_id'], 'right': right['candidate_id'], 'title_similarity': similarity})
                for candidate in (left, right):
                    candidate['review_reasons'] = sorted(set(candidate['review_reasons'] + ['similar_thesis_title']))
                    candidate['status'] = 'quarantined'
    by_id = {c['candidate_id']: c for c in candidates}
    for row in sources:
        if row['candidate_ids'] and any(by_id[c]['status'] == 'quarantined' for c in row['candidate_ids']):
            row.update(status='quarantined', reason='candidate_requires_review')
    for candidate in candidates:
        review.append({'source_id': candidate['source_id'], 'candidate_id': candidate['candidate_id'],
                       'reason': ';'.join(candidate['review_reasons'])})
    with (run / 'bronze/student_candidates.jsonl').open('w', encoding='utf-8') as stream:
        for candidate in candidates:
            stream.write(json.dumps(candidate, ensure_ascii=False) + '\n')
    _csv(run / 'reports/source_extraction_quality.csv', sources)
    _csv(run / 'reports/pdf_extraction_quality.csv', [r for r in sources if r['format'] == 'pdf'])
    _csv(run / 'reports/archive_member_manifest.csv', members)
    _csv(run / 'reports/review_queue.csv', review)
    _csv(run / 'reports/source_to_entity_mapping.csv', [{k: r[k] for k in ('source_id', 'source_file', 'status', 'candidate_ids')} for r in sources])
    _csv(run / 'reports/pdf_to_entity_mapping.csv', [{k: r[k] for k in ('source_id', 'source_file', 'status', 'candidate_ids')} for r in sources if r['format'] == 'pdf'])
    _json(run / 'reports/near_duplicate_candidates.json', near_duplicates)
    _json(run / 'reports/evidence_errors.json', evidence_errors)
    code_unchanged = code_hashes == _code_hashes()
    complete = len(original_ids) == len(originals) and all(s['status'] in {'extracted', 'quarantined', 'failed'} for s in sources)
    complete = complete and code_unchanged and digest(inventory_path) == inventory_hash
    report = {'phase': 1, 'status': 'verified' if complete and not evidence_errors else 'blocked',
              'scope': 'Extraction conservation and evidence gate; not gold approval or extraction accuracy certification',
              'can_start_phase2': complete and not evidence_errors, 'run_id': run_id, 'run_dir': str(run),
              'original_sources_accounted': len(original_ids), 'expected_original_sources': len(originals),
              'source_records_including_derived': len(sources), 'source_statuses': dict(Counter(s['status'] for s in sources)),
              'candidate_records': len(candidates), 'evidence_errors': len(evidence_errors),
              'page_statuses': dict(Counter(p['status'] for p in outcomes)),
              'ocr_pages': sum(p.get('ocr_attempted', False) for p in outcomes), 'archive_members': len(members),
              'archive_member_statuses': dict(Counter(m['status'] for m in members)),
              'field_coverage': {field: sum(field in c['fields'] for c in candidates) for field in
                                 ('student_id', 'student_name', 'thesis_title', 'thesis_abstract', 'thesis_keywords')},
              'human_approved_records': 0, 'unique_students': None,
              'input_inventory_sha256': inventory_hash, 'code_unchanged_during_run': code_unchanged,
              'source_code_sha256': code_hashes,
              'created_at': datetime.now(timezone.utc).isoformat()}
    _json(run / 'reports/phase1_gate.json', report)
    _json(run / 'manifest.json', {'gate': report, 'artifacts': [
        {'path': str(p.relative_to(run)), 'sha256': digest(p)} for parent in ('bronze', 'reports')
        for p in sorted((run / parent).iterdir()) if p.is_file()]})
    # Original run is immutable evidence; these are explicit latest-artifact copies.
    for parent in ('bronze', 'reports'):
        (output / parent).mkdir(exist_ok=True)
        for path in (run / parent).iterdir():
            if path.is_file():
                shutil.copy2(path, output / parent / path.name)
    return report
