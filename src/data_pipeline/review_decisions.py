"""Explicit curator decisions bound to exact extracted records, never auto-approval."""
import copy
import hashlib
import json
import math
from collections import Counter
from datetime import datetime


def record_hash(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def apply_decisions(records: list[dict], decisions: list[dict], *, correction_validator=None):
    result = copy.deepcopy(records)
    index = {row['record_id']: row for row in result}
    if len(index) != len(result):
        raise ValueError('duplicate_input_record_ids')
    errors = []
    counts = Counter(d.get('record_id') for d in decisions)
    for decision in decisions:
        key = decision.get('record_id')
        code = None
        row = index.get(key)
        if row is None:
            code = 'unknown_record'
        elif counts[key] != 1:
            code = 'duplicate_review_decision'
        elif decision.get('record_sha256') != record_hash(row):
            code = 'stale_record_review'
        elif not str(decision.get('reviewer', '')).strip():
            code = 'reviewer_required'
        elif decision.get('decision') not in {'approve', 'reject', 'needs_review'}:
            code = 'invalid_review_decision'
        try:
            timestamp = datetime.fromisoformat(decision.get('reviewed_at', '').replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                code = code or 'review_timezone_required'
        except (ValueError, AttributeError):
            code = code or 'review_timestamp_invalid'
        confidence = decision.get('evidence_confidence')
        if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                                       or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            code = code or 'invalid_evidence_confidence'
        changed = copy.deepcopy(row) if row else None
        corrections = decision.get('corrections', {})
        removals = decision.get('remove_fields', [])
        if removals and not code:
            if (row.get('entity_type') != 'students' or not isinstance(removals, list)
                    or any(not isinstance(field, str) for field in removals)
                    or len(removals) != len(set(removals))
                    or not set(removals) <= {'thesis_abstract', 'thesis_keywords'}
                    or any(field not in row['fields'] for field in removals)
                    or correction_validator is None):
                code = 'invalid_optional_field_removal'
        if (corrections or removals) and not code:
            entity = row.get('entity_type')
            allowed = ({'student_id', 'student_name', 'thesis_title', 'thesis_abstract', 'thesis_keywords'}
                       if entity == 'students' else {'research_topics', 'teaching_topics'} if entity == 'advisors' else set())
            if (not allowed or not isinstance(corrections, dict)
                    or not set(corrections) <= allowed or correction_validator is None):
                code = 'correction_evidence_validator_required'
            else:
                if entity == 'students':
                    changed['fields'].update(corrections)
                    for field in removals:
                        changed['fields'].pop(field)
                else:
                    changed.update(corrections)
                if correction_validator(row, changed):
                    code = 'correction_source_evidence_invalid'
        if code:
            errors.append({'record_id': key, 'code': code})
            continue
        changed['review_status'] = {'approve': 'approved', 'reject': 'rejected', 'needs_review': 'needs_review'}[decision['decision']]
        previous_audit = copy.deepcopy(row.get('review_audit'))
        actual_changes = {field for field in corrections
                          if (row.get('fields', {}).get(field) != changed.get('fields', {}).get(field)
                              if row.get('entity_type') == 'students' else row.get(field) != changed.get(field))}
        corrected_fields = actual_changes | set(removals) | set((previous_audit or {}).get('corrected_fields', []))
        changed['review_audit'] = {'reviewer': decision['reviewer'], 'reviewed_at': decision['reviewed_at'],
                                   'record_sha256': decision['record_sha256'], 'decision': decision['decision'],
                                   'notes': str(decision.get('notes', '')), 'evidence_confidence': confidence,
                                   'corrected_fields': sorted(corrected_fields),
                                   'removed_fields': sorted(set(removals) | set((previous_audit or {}).get('removed_fields', []))),
                                   'previous_review_audit': previous_audit}
        index[key].clear()
        index[key].update(changed)
    return result, errors
