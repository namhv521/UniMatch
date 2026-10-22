import copy
import hashlib
import json

import pytest

from src.data_pipeline.review_decisions import record_hash, apply_decisions


def record():
    return {'record_id': 'technical-record', 'entity_type': 'students', 'source_sha256': 'a'*64,
            'review_status': 'needs_review', 'fields': {'thesis_title': {'value': 'Technical fixture'}}}


def decision(row, **overrides):
    return {'record_id': row['record_id'], 'record_sha256': record_hash(row), 'decision': 'approve',
            'reviewer': 'fixture-reviewer', 'reviewed_at': '2026-10-21T12:00:00+00:00', **overrides}


def test_no_approval_without_explicit_bound_decision():
    row = record()
    result, errors = apply_decisions([row], [])
    assert result[0]['review_status'] == 'needs_review' and errors == []
    result, errors = apply_decisions([row], [decision(row)])
    assert result[0]['review_status'] == 'approved' and not errors
    assert row['review_status'] == 'needs_review'
    assert result[0]['review_audit']['record_sha256'] == record_hash(row)


def test_stale_duplicate_or_unattributed_reviews_cannot_approve():
    row = record()
    stale = decision(row)
    changed = copy.deepcopy(row)
    changed['fields']['thesis_title']['value'] = 'Changed extraction'
    result, errors = apply_decisions([changed], [stale])
    assert result[0]['review_status'] != 'approved' and errors
    for reviews in ([decision(row), decision(row)], [decision(row, reviewer='')],
                    [decision(row, reviewed_at='2026-10-21')], [decision(row, record_id='unknown')]):
        result, errors = apply_decisions([row], reviews)
        assert result[0]['review_status'] != 'approved' and errors


def test_corrections_require_source_evidence_validator():
    row = record()
    review = decision(row, corrections={'thesis_title': {'value': 'Corrected'}})
    result, errors = apply_decisions([row], [review])
    assert result[0]['review_status'] != 'approved' and errors
    result, errors = apply_decisions([row], [review], correction_validator=lambda old, new: ['no source proof'])
    assert result[0]['review_status'] != 'approved' and errors


def test_record_hash_is_canonical_and_does_not_depend_on_dict_order():
    row = record()
    assert record_hash(row) == record_hash(dict(reversed(list(row.items()))))


def test_advisor_correction_can_remove_metadata_but_not_add_expertise():
    row = {'record_id': 'technical-faculty', 'entity_type': 'advisors',
           'review_status': 'needs_review', 'research_topics': ['Databases', 'Google Scholar'],
           'teaching_topics': [], 'evidence': ['original fixture receipts']}
    from src.data_pipeline.reconcile import validate_advisor_correction
    proposal = decision(row, decision='needs_review', corrections={'research_topics': ['Databases']})
    result, errors = apply_decisions([row], [proposal], correction_validator=validate_advisor_correction)
    assert not errors and result[0]['research_topics'] == ['Databases']
    assert result[0]['review_status'] == 'needs_review' and result[0]['evidence'] == row['evidence']
    proposal['corrections']['research_topics'] = ['Unobserved expertise']
    result, errors = apply_decisions([row], [proposal], correction_validator=validate_advisor_correction)
    assert errors and result[0]['research_topics'] == row['research_topics']


def test_only_optional_student_fields_can_be_explicitly_removed():
    row = record()
    row['fields']['thesis_abstract'] = {'value': 'Misclassified technical fixture'}
    proposal = decision(row, decision='needs_review', remove_fields=['thesis_abstract'])
    result, errors = apply_decisions([row], [proposal], correction_validator=lambda old, new: [])
    assert not errors and 'thesis_abstract' not in result[0]['fields']
    assert result[0]['review_audit']['corrected_fields'] == ['thesis_abstract']
    proposal['remove_fields'] = ['thesis_title']
    result, errors = apply_decisions([row], [proposal], correction_validator=lambda old, new: [])
    assert errors and result[0]['fields'] == row['fields']


def test_owner_review_preserves_source_correction_history():
    row = record()
    proposal = decision(row, decision='needs_review', corrections={'thesis_title': {'value': 'Evidence corrected fixture'}})
    proposed, errors = apply_decisions([row], [proposal], correction_validator=lambda old, new: [])
    assert not errors
    approved, errors = apply_decisions(proposed, [decision(proposed[0])])
    assert not errors and approved[0]['review_status'] == 'approved'
    assert approved[0]['review_audit']['corrected_fields'] == ['thesis_title']
    assert approved[0]['review_audit']['previous_review_audit']['decision'] == 'needs_review'


def test_noop_field_correction_cannot_claim_resolution():
    row = record()
    proposal = decision(row, decision='needs_review', corrections=copy.deepcopy(row['fields']))
    result, errors = apply_decisions([row], [proposal], correction_validator=lambda old, new: [])
    assert not errors and result[0]['review_audit']['corrected_fields'] == []
