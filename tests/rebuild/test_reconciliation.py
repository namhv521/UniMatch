from src.data_pipeline.reconcile import canonicalize_students


def candidate(key, source_hash, student_id='11223344'):
    return {'candidate_id': key, 'source_id': key, 'source_sha256': source_hash,
            'source_file': f'{key}.pdf', 'review_status': 'needs_review',
            'fields': {'student_id': {'value': student_id}}, 'review_reasons': []}


def test_only_identical_byte_sources_with_same_observed_identity_are_collapsed():
    rows, decisions = canonicalize_students([candidate('b', 'a'*64), candidate('a', 'a'*64), candidate('c', 'b'*64)])
    assert len(rows) == 2
    assert rows[0]['record_id'] == 'a'
    assert rows[0]['source_aliases'][0]['source_id'] == 'b'
    assert all(row['review_status'] == 'needs_review' for row in rows)
    assert all('conflicting_source_versions' in row['review_reasons'] for row in rows)
    assert len(decisions) == 1 and decisions[0]['decision'] == 'identical_bytes_same_observed_id'


def test_missing_identity_never_deduplicates_entities_by_shared_content():
    first, second = candidate('a', 'a'*64), candidate('b', 'a'*64)
    first['fields'], second['fields'] = {}, {}
    rows, decisions = canonicalize_students([first, second])
    assert len(rows) == 2 and decisions == []
