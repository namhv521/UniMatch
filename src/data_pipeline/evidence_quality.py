"""Transparent owner-selected evidence rubric; no proficiency or probability estimate."""
from __future__ import annotations

import hashlib
import json
import re


RUBRIC_VERSION = 'source-span-semantic-v1'
CHECKS = ('source', 'span', 'semantic')
CHECK_STATES = {'pass', 'fail', 'uncertain', 'pending'}
IDENTITY_FIELDS = ('tag', 'group', 'output_column', 'source_field', 'matched_text',
                   'start', 'end', 'source_sha256', 'evidence_sha256')


def _hash(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def evaluate_tag_checks(record_id: str, record_sha256: str, tags: list[dict], *,
                        rubric_version: str = RUBRIC_VERSION) -> dict:
    """Score completed explicit checks as passed/total; unresolved checks remain null.

    The caller defines auditable tag units (e.g. distinct CSV column/tag pairs),
    supplies the evidence hash and completed checks, and preserves supporting
    occurrences externally. Missing or uncertain checks never become a pass.
    """
    if (not isinstance(record_id, str) or not record_id or not isinstance(record_sha256, str)
            or not re.fullmatch(r'[0-9a-f]{64}', record_sha256)):
        raise ValueError('invalid_record_binding')
    results, identities = [], set()
    for tag in tags:
        if not isinstance(tag, dict) or any(not isinstance(tag.get(k), str) or not tag[k]
                                             for k in ('tag', 'group', 'output_column')):
            raise ValueError('invalid_tag_identity')
        identity = {key: tag[key] for key in IDENTITY_FIELDS if key in tag}
        content_hash = _hash(identity)
        tag_id = _hash({'record_id': record_id, 'identity': identity})
        unit = (tag['output_column'], tag['tag'])
        if unit in identities:
            raise ValueError('duplicate_tag_identity')
        identities.add(unit)
        provided = tag.get('checks', {})
        if not isinstance(provided, dict) or set(provided) - set(CHECKS):
            raise ValueError('invalid_check_fields')
        checks = {key: provided.get(key, 'pending') for key in CHECKS}
        if any(not isinstance(value, str) or value not in CHECK_STATES for value in checks.values()):
            raise ValueError('invalid_check_status')
        # A known failure does not certify completion of a separate pending check.
        status = ('pending' if any(v in {'uncertain', 'pending'} for v in checks.values())
                  else 'pass' if all(v == 'pass' for v in checks.values()) else 'fail')
        results.append({**tag, 'tag_id': tag_id, 'tag_sha256': content_hash, 'checks': checks, 'status': status})
    passed = sum(tag['status'] == 'pass' for tag in results)
    failed = sum(tag['status'] == 'fail' for tag in results)
    pending = sum(tag['status'] == 'pending' for tag in results)
    result = {'record_id': record_id, 'record_sha256': record_sha256, 'rubric_version': rubric_version,
              'metric': 'evidence_check_fraction', 'is_probability': False, 'is_proficiency': False,
              'passed': passed, 'total': len(results), 'failed': failed, 'pending': pending,
              'score': passed / len(results) if results and not pending else None, 'tags': results}
    result['assessment_sha256'] = _hash(result)
    return result
