"""Explicit owner receipt and per-record evidence gates, using technical fixtures only."""
import json
import hashlib

import pytest

from src.data_pipeline.review_decisions import record_hash


def test_acceptance_never_promotes_pending_or_conflicting_records():
    from src.data_pipeline.acceptance import build_owner_decisions
    records = [{'record_id': key, 'entity_type': 'students'} for key in ('good', 'conflict', 'pending', 'empty')]
    eligibility = [{'record_id': r['record_id'], 'record_sha256': record_hash(r),
                    'eligible_core': r['record_id'] != 'conflict', 'blocking_codes': []} for r in records]
    quality = [{'record_id': r['record_id'], 'record_sha256': record_hash(r), 'rubric_version': 'source-span-semantic-v1',
                'total': 0 if r['record_id'] == 'empty' else 2, 'passed': 0 if r['record_id'] in {'pending', 'empty'} else 2,
                'pending': 2 if r['record_id'] == 'pending' else 0, 'failed': 0,
                'score': None if r['record_id'] in {'pending', 'empty'} else 1.0} for r in records]
    receipt = {'reviewer': 'owner:technical-fixture', 'recorded_at': '2026-10-21T16:00:00Z',
               'package_manifest_sha256': 'a'*64, 'rubric_version': 'source-span-semantic-v1'}
    decisions = build_owner_decisions(records, eligibility, quality, receipt, receipt_sha256='b'*64)
    assert {d['record_id']: d['decision'] for d in decisions} == {
        'good': 'approve', 'conflict': 'needs_review', 'pending': 'needs_review', 'empty': 'approve'}
    assert decisions[0]['evidence_confidence'] == 1.0 and decisions[-1]['evidence_confidence'] is None
    assert all(json.loads(d['notes'])['authority_receipt_sha256'] == 'b'*64 for d in decisions)
    quality[0]['score'] = 0.8  # The rubric fraction cannot be supplied independently of its counts.
    with pytest.raises(ValueError, match='quality_score_mismatch'):
        build_owner_decisions(records, eligibility, quality, receipt, receipt_sha256='b'*64)


def test_stale_incomplete_or_duplicate_evidence_cannot_approve():
    from src.data_pipeline.acceptance import build_owner_decisions
    records = [{'record_id': 'fixture'}]
    eligibility = [{'record_id': 'fixture', 'record_sha256': 'wrong', 'eligible_core': True}]
    receipt = {'reviewer': 'owner:technical-fixture', 'recorded_at': '2026-10-21T16:00:00Z',
               'package_manifest_sha256': 'a'*64, 'rubric_version': 'source-span-semantic-v1'}
    with pytest.raises(ValueError):
        build_owner_decisions(records, eligibility, [], receipt, receipt_sha256='b'*64)


def test_owner_package_must_still_match_exact_approved_bytes(tmp_path):
    from src.data_pipeline.acceptance import verify_owner_package
    package = tmp_path / 'approved'
    package.mkdir()
    report = package / 'report.md'
    report.write_text('Technical fixture report')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = package / 'package_manifest.json'
    manifest.write_text(json.dumps({'phase3_run_id': 'fixture-run', 'artifacts': [
        {'path': 'report.md', 'sha256': digest(report)}]}))
    receipt = tmp_path / 'owner.json'
    receipt.write_text(json.dumps({'package_path': str(package), 'package_manifest_sha256': digest(manifest),
                                   'approved_staging_run_id': 'fixture-run',
                                   'authority_type': 'explicit_owner_messages_in_current_conversation',
                                   'owner_quote': 'Technical fixture only'}))
    assert verify_owner_package(receipt)[1] == package
    report.write_text('Changed technical fixture report')
    with pytest.raises(ValueError, match='approved_package_artifact_modified'):
        verify_owner_package(receipt)


def test_quality_rehash_cannot_launder_wrong_source_or_span():
    from src.data_pipeline.acceptance import validate_quality_binding
    from src.data_pipeline.evidence_quality import evaluate_tag_checks
    record = {'record_id': 'fixture', 'entity_type': 'students', 'source_sha256': 'a'*64,
              'fields': {'thesis_title': {'value': 'Python'}}, 'technology_mentions': []}
    mention = {'tag': 'python', 'group': 'programming_languages', 'output_column': 'programming_languages',
               'source_field': 'thesis_title', 'matched_text': 'Python', 'start': 0, 'end': 6,
               'evidence_type': 'inferred_from_thesis', 'ref_indexes': [0]}
    refs = [{'snippet': 'Python'}]
    normalization = [{'record_id': 'fixture', 'source': {'source_sha256': 'a'*64, 'tags': [mention], 'refs': refs}}]
    occurrence = {**mention, 'source_text': 'Python', 'refs': refs,
                  'checks': {'source': 'pass', 'span': 'pass', 'semantic': 'pass'}}
    unit = {'tag': 'python', 'group': 'programming_languages', 'output_column': 'programming_languages',
            'source_sha256': 'a'*64, 'evidence_sha256': record_hash([occurrence]), 'occurrences': [occurrence],
            'checks': occurrence['checks']}
    quality = [evaluate_tag_checks('fixture', record_hash(record), [unit])]
    validate_quality_binding([record], normalization, quality)
    unit['source_sha256'] = 'b'*64
    quality = [evaluate_tag_checks('fixture', record_hash(record), [unit])]
    with pytest.raises(ValueError, match='quality_source_binding_mismatch'):
        validate_quality_binding([record], normalization, quality)
    unit['source_sha256'] = 'a'*64
    occurrence['start'] = 1
    unit['evidence_sha256'] = record_hash([occurrence])
    quality = [evaluate_tag_checks('fixture', record_hash(record), [unit])]
    with pytest.raises(ValueError, match='quality_occurrence_binding_mismatch'):
        validate_quality_binding([record], normalization, quality)
    occurrence['start'] = 0
    occurrence['checks']['semantic'] = 'not_assessed'
    unit['checks'] = {'source': 'pass', 'span': 'pass', 'semantic': 'pass'}
    unit['evidence_sha256'] = record_hash([occurrence])
    quality = [evaluate_tag_checks('fixture', record_hash(record), [unit])]
    with pytest.raises(ValueError, match='quality_occurrence_check_status_invalid'):
        validate_quality_binding([record], normalization, quality)
