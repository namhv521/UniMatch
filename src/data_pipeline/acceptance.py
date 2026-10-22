"""Translate explicit owner ratification into bound, conservative record decisions."""
import json
import hashlib
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .review_decisions import record_hash


def verify_owner_package(receipt_path):
    receipt = receipt_path if isinstance(receipt_path, dict) else json.loads(Path(receipt_path).read_text(encoding='utf-8'))
    package = Path(receipt['package_path']).resolve()
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    path = package / 'package_manifest.json'
    if (digest(path) != receipt['package_manifest_sha256']
            or receipt.get('authority_type') != 'explicit_owner_messages_in_current_conversation'
            or not receipt.get('owner_quote', '').strip()):
        raise ValueError('owner_receipt_package_binding_invalid')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest['phase3_run_id'] != receipt['approved_staging_run_id']:
        raise ValueError('owner_receipt_run_mismatch')
    for item in manifest['artifacts']:
        artifact = (package / item['path']).resolve()
        if not artifact.is_relative_to(package) or not artifact.is_file() or digest(artifact) != item['sha256']:
            raise ValueError('approved_package_artifact_modified')
    return receipt, package


def validate_quality_binding(records, normalization, quality):
    """Bind every assessed occurrence to canonical normalization, source text and refs."""
    from .evidence_quality import CHECKS, CHECK_STATES, evaluate_tag_checks
    index = {r['record_id']: r for r in records}
    canonical = {r['record_id']: r['source'] for r in normalization}
    if len(quality) != len(index) or {r['record_id'] for r in quality} != set(index):
        raise ValueError('quality_record_coverage_mismatch')
    for assessment in quality:
        key = assessment['record_id']
        record, source = index[key], canonical[key]
        if assessment['record_sha256'] != record_hash(record):
            raise ValueError('stale_record_assessment')
        grouped = defaultdict(list)
        for mention in source.get('tags', []):
            grouped[(mention['output_column'], mention['tag'])].append(mention)
        units = assessment['tags']
        if {(u['output_column'], u['tag']) for u in units} != set(grouped):
            raise ValueError('quality_tag_coverage_mismatch')
        for unit in units:
            expected = grouped[(unit['output_column'], unit['tag'])]
            if unit['source_sha256'] != record['source_sha256'] or any(m['group'] != unit['group'] for m in expected):
                raise ValueError('quality_source_binding_mismatch')
            occurrences = unit['occurrences']
            # All normalization keys are authoritative; assessment-only context is extra.
            signatures = lambda rows: Counter(record_hash({k: r.get(k) for k in expected[0]}) for r in rows)
            if signatures(occurrences) != signatures(expected) or unit['evidence_sha256'] != record_hash(occurrences):
                raise ValueError('quality_occurrence_binding_mismatch')
            for occurrence in occurrences:
                checks = occurrence.get('checks', {})
                if (not isinstance(checks, dict) or set(checks) - set(CHECKS)
                        or any(not isinstance(checks.get(check, 'pending'), str)
                               or checks.get(check, 'pending') not in CHECK_STATES for check in CHECKS)):
                    raise ValueError('quality_occurrence_check_status_invalid')
                field = occurrence['source_field']
                if field == 'technology_mentions':
                    texts = [str(m['value']) for m in record.get(field, [])]
                elif record.get('entity_type') == 'students':
                    texts = [str(record['fields'].get(field, {}).get('value', ''))]
                else:
                    texts = record.get(field, [])
                text = occurrence['source_text']
                if (text not in texts or text[occurrence['start']:occurrence['end']] != occurrence['matched_text']
                        or occurrence['refs'] != [source['refs'][i] for i in occurrence['ref_indexes']]):
                    raise ValueError('quality_occurrence_binding_mismatch')
            for check in ('source', 'span', 'semantic'):
                states = {o['checks'].get(check, 'pending') for o in occurrences}
                status = 'uncertain' if states & {'uncertain', 'pending'} else 'fail' if 'fail' in states else 'pass'
                if unit['checks'].get(check) != status:
                    raise ValueError('quality_occurrence_check_aggregation_mismatch')
        checked = evaluate_tag_checks(key, record_hash(record), units)
        if any(checked[field] != assessment[field] for field in
               ('total', 'passed', 'failed', 'pending', 'score', 'assessment_sha256')):
            raise ValueError('quality_assessment_recomputation_mismatch')


def build_owner_decisions(records, eligibility, quality, receipt, *, receipt_sha256):
    """Unknown evidence and unresolved identities remain outside approved gold."""
    timestamp = datetime.fromisoformat(receipt['recorded_at'].replace('Z', '+00:00'))
    if (timestamp.tzinfo is None or not receipt['reviewer'].startswith('owner:')
            or not all(re.fullmatch('[a-f0-9]{64}', value) for value in
                       (receipt_sha256, receipt['package_manifest_sha256']))
            or receipt['rubric_version'] != 'source-span-semantic-v1'):
        raise ValueError('invalid_owner_authority_receipt')
    index = {r['record_id']: r for r in records}
    if len(index) != len(records):
        raise ValueError('duplicate_acceptance_record')
    assessments = []
    for rows in (eligibility, quality):
        mapping = {row['record_id']: row for row in rows}
        if len(mapping) != len(rows) or set(mapping) != set(index):
            raise ValueError('assessment_coverage_mismatch')
        if any(row.get('record_sha256') != record_hash(index[key]) for key, row in mapping.items()):
            raise ValueError('stale_record_assessment')
        assessments.append(mapping)
    eligible, scored = assessments
    decisions = []
    for key, record in index.items():
        assessment, q = eligible[key], scored[key]
        counts = [q.get(field) for field in ('total', 'passed', 'failed', 'pending')]
        if (any(type(value) is not int or value < 0 for value in counts)
                or q.get('rubric_version') != receipt['rubric_version']
                or q['passed'] + q['failed'] + q['pending'] != q['total']):
            raise ValueError('invalid_quality_counts')
        expected = q['passed']/q['total'] if q['total'] and not q['pending'] else None
        score = q.get('score')
        if (type(score) is bool or (score is not None and
                (not isinstance(score, (int, float)) or not math.isfinite(score)))
                or score != expected):
            raise ValueError('quality_score_mismatch')
        accepted = (assessment.get('eligible_core') is True and not assessment.get('blocking_codes')
                    and q['failed'] == 0 and q['pending'] == 0)
        notes = {'authority_receipt_sha256': receipt_sha256,
                 'approved_package_manifest_sha256': receipt['package_manifest_sha256'],
                 'review_kind': 'owner_ratified_agent_evidence_report',
                 'rubric_version': receipt['rubric_version'],
                 'quality_counts': {field: q[field] for field in ('total', 'passed', 'failed', 'pending')},
                 'assessment_sha256': q.get('assessment_sha256'),
                 'blocking_codes': assessment.get('blocking_codes', []),
                 'claim_scope': 'Evidence quality only; no proficiency, probability or supervisory eligibility claim.'}
        decisions.append({'record_id': key, 'record_sha256': record_hash(record),
                          'decision': 'approve' if accepted else 'needs_review',
                          'reviewer': receipt['reviewer'], 'reviewed_at': receipt['recorded_at'],
                          'evidence_confidence': score, 'notes': json.dumps(notes, ensure_ascii=False)})
    return decisions
