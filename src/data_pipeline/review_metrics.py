"""Field accuracy from explicit human labels; pending labels never become scores."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REVIEW_FIELDS = {'student_id', 'student_name', 'thesis_title', 'thesis_abstract', 'thesis_keywords', 'technology_mentions'}

def sample_candidates(candidates):
    """Deterministic diagnostic sample, covering observed source layouts."""
    ordered = sorted(candidates, key=lambda row: row['candidate_id'])
    chosen = {}
    predicates = {
        'word': lambda r: r.get('source_file', '').lower().endswith('.docx'),
        'archive_derived': lambda r: bool(r.get('archive_chain')),
        'missing_id': lambda r: 'student_id' not in r['fields'],
        'missing_title': lambda r: 'thesis_title' not in r['fields'],
        'unverified_id': lambda r: 'unverified_student_id' in r.get('review_reasons', []),
        'abstract_present': lambda r: 'thesis_abstract' in r['fields'],
        'multiblock_title': lambda r: len(r['fields'].get('thesis_title', {}).get('evidence', [])) > 1,
        'ocr_field': lambda r: any(any(marker in e.get('extraction_method', '').lower() for marker in ('ocr', 'tesseract'))
                                  for f in r['fields'].values() for e in f.get('evidence', [])),
    }
    for stratum, predicate in predicates.items():
        for row in [r for r in ordered if predicate(r)][:2]:
            chosen.setdefault(row['candidate_id'], set()).add(stratum)
    for row in ordered:
        if len(chosen) >= min(14, len(ordered)):
            break
        chosen.setdefault(row['candidate_id'], set()).add('deterministic_fill')
    return chosen


def evaluate_sample(path, candidates, run_id):
    index = {r['candidate_id']: r for r in candidates}
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    counts, errors, seen, incorrect, uncertain = defaultdict(Counter), [], set(), [], []
    reviewed = 0
    review_kinds = Counter()
    ratification_receipts = set()
    for number, row in enumerate(rows, 2):
        if row.get('review_status') != 'reviewed':
            continue
        key, field = row.get('candidate_id'), row.get('field_name')
        candidate = index.get(key)
        code = None
        if field not in REVIEW_FIELDS:
            code = 'unknown_sample_field'
        elif candidate is None or row.get('run_id') != run_id:
            code = 'sample_snapshot_mismatch'
        elif row.get('source_sha256') != candidate['source_sha256']:
            code = 'sample_source_hash_mismatch'
        elif (key, field) in seen:
            code = 'duplicate_sample_field'
        else:
            seen.add((key, field))
            if field == 'technology_mentions':
                expected = [m['value'] for m in candidate.get('technology_mentions', [])]
                try:
                    matches = json.loads(row.get('candidate_value', '[]')) == expected
                except ValueError:
                    matches = False
            else:
                expected = str(candidate['fields'].get(field, {}).get('value', ''))
                matches = row.get('candidate_value', '') == expected
            if not matches:
                code = 'sample_extracted_value_changed'
        try:
            timestamp = datetime.fromisoformat(row.get('reviewed_at', '').replace('Z', '+00:00'))
            if timestamp.tzinfo is None or not row.get('reviewer', '').strip():
                code = code or 'sample_reviewer_or_timezone_missing'
        except ValueError:
            code = code or 'sample_review_date_invalid'
        verdict = row.get('field_verdict')
        if verdict not in {'correct', 'incorrect', 'missing_in_source', 'not_extracted', 'uncertain'}:
            code = code or 'sample_verdict_invalid'
        if verdict == 'missing_in_source' and row.get('candidate_value') not in {'', '[]'}:
            code = code or 'nonempty_value_cannot_be_missing_in_source'
        if code:
            errors.append({'row': number, 'candidate_id': key, 'field': field, 'code': code})
            continue
        counts[field][verdict] += 1
        reviewed += 1
        review_kinds[row.get('review_kind') or 'direct_curator_review'] += 1
        if row.get('review_kind') == 'owner_ratified_agent_report':
            ratification_receipts.add(row.get('authority_receipt_sha256', ''))
        if verdict in {'incorrect', 'not_extracted'}:
            incorrect.append({'candidate_id': key, 'field': field})
        elif verdict == 'uncertain':
            uncertain.append({'candidate_id': key, 'field': field})
    fields = {}
    for field, counter in counts.items():
        known = sum(counter.values()) - counter['uncertain']
        fields[field] = {'counts': dict(counter),
                         'accuracy': (counter['correct']+counter['missing_in_source'])/known if known else None,
                         'known_labels': known, 'uncertain': counter['uncertain']}
    coverage = defaultdict(set)
    for row in rows:
        coverage[row.get('candidate_id')].add(row.get('field_name'))
    complete_coverage = bool(coverage) and all(value == REVIEW_FIELDS for value in coverage.values())
    expected_ids = set(sample_candidates(candidates))
    package_matches = set(coverage) == expected_ids
    if not package_matches:
        errors.append({'code': 'sample_package_coverage_mismatch',
                       'expected_candidates': len(expected_ids), 'actual_candidates': len(coverage)})
    return {'complete': bool(rows) and complete_coverage and reviewed == len(rows) and not errors,
            'run_id': run_id, 'sample_rows': len(rows), 'reviewed_rows': reviewed,
            'fields': fields, 'errors': errors, 'incorrect_fields': incorrect,
            'uncertain_fields': uncertain,
            'accuracy_definition': '(correct + correctly missing in source) / known reviewed field labels; uncertain excluded',
            'complete_field_coverage': complete_coverage,
            'expected_package_coverage': package_matches,
            'uncertain_labels': sum(c['uncertain'] for c in fields.values()),
            'review_kind_counts': dict(review_kinds),
            'ratification_receipt_sha256s': sorted(ratification_receipts),
            'sampling_limitation': 'Stratified diagnostic sample, not a random estimate of full-corpus accuracy'}
