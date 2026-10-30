"""Technical-only student group leakage and deterministic split contracts."""
import copy
import hashlib

import pytest

from src.features.rebuild_splits import make_grouped_split


def student(key, title=None, source=None, **extra):
    return {'student_id': key, 'thesis_title': title or ('Distinct technical topic ' + key),
            'source_sha256': source or hashlib.sha256(key.encode()).hexdigest(), **extra}


def independent():
    return [student('A', 'Computer vision for fruit disease'),
            student('B', 'Financial forecasting using stochastic calculus'),
            student('C', 'Network security cryptographic protocols'),
            student('D', 'Database transaction isolation architectures'),
            student('E', 'Human computer interface usability evaluation')]


def test_reproducible_under_input_reordering_and_never_fabricates_temporal_claims():
    rows = independent()
    result = make_grouped_split(rows)
    assert result == make_grouped_split(list(reversed(rows)))
    assert set(result['assignments']) == {r['student_id'] for r in rows}
    assert set(result['assignments'].values()) == {'train', 'validation', 'test'}
    assert result['metadata']['split_kind'] == 'non_temporal_grouped'
    assert result['metadata']['near_title_threshold'] == .92
    assert result['metadata']['chronological_validation'] is False
    assert result['metadata']['test_policy'] == 'untouched_until_final_evaluation'
    assert result['metadata']['identity_fields_are_features'] is False
    assert result['metadata']['limitations']


def test_source_alias_exact_and_near_title_connected_components_never_cross_splits():
    rows = independent()
    rows.extend([
        student('A-source-copy', 'An unrelated title from identical source', source=rows[0]['source_sha256']),
        student('A-alias-copy', 'Another unrelated archival title',
                source_aliases=[{'source_sha256': rows[0]['source_sha256']}]),
        student('A-title-copy', '  COMPUTER VISION: for fruit disease! '),
        student('A-near-copy', 'Computer vision for fruit diseases'),
    ])
    before = copy.deepcopy(rows)
    result = make_grouped_split(rows, seed=17)
    keys = ['A', 'A-source-copy', 'A-alias-copy', 'A-title-copy', 'A-near-copy']
    assert len({result['groups'][key] for key in keys}) == 1
    assert len({result['assignments'][key] for key in keys}) == 1
    assert rows == before
    assert result['metadata']['group_count'] == 5
    assert result['metadata']['group_counts'] == {'train': 3, 'validation': 1, 'test': 1}


def test_exactly_three_independent_groups_keep_all_partitions_nonempty():
    result = make_grouped_split(independent()[:3], train_fraction=.98, validation_fraction=.01)
    assert result['metadata']['group_counts'] == {'train': 1, 'validation': 1, 'test': 1}


def test_asymmetric_sequence_matcher_cannot_hide_a_near_duplicate():
    # SequenceMatcher gives .88 in one direction and .92 in the other.
    rows = independent()[:3] + [student('X', 'x' * 21 + 'tide'), student('Y', 'x' * 21 + 'diet')]
    result = make_grouped_split(rows)
    assert result['groups']['X'] == result['groups']['Y']
    assert result['assignments']['X'] == result['assignments']['Y']


@pytest.mark.parametrize('rows', [[], independent()[:1], independent()[:2],
                                [student('A', 'same title'), student('B', 'same title'), student('C', 'same title')]])
def test_too_few_independent_groups_explicitly_block(rows):
    with pytest.raises(ValueError, match='at_least_three_independent_groups'):
        make_grouped_split(rows)


@pytest.mark.parametrize('bad', [None, '', '  ', 123, True])
def test_invalid_student_identity_is_rejected(bad):
    rows = independent()
    rows[0]['student_id'] = bad
    with pytest.raises(ValueError, match='invalid_student_id'):
        make_grouped_split(rows)


def test_duplicate_student_identity_is_rejected_even_with_distinct_documents():
    rows = independent()
    rows[1]['student_id'] = rows[0]['student_id']
    with pytest.raises(ValueError, match='duplicate_student_id'):
        make_grouped_split(rows)


@pytest.mark.parametrize('options', [dict(train_fraction=0), dict(validation_fraction=0),
                                  dict(train_fraction=.9, validation_fraction=.2),
                                  dict(train_fraction=float('nan')), dict(validation_fraction=True), dict(seed=True)])
def test_invalid_split_configuration_is_rejected(options):
    with pytest.raises(ValueError, match='invalid_split_configuration'):
        make_grouped_split(independent(), **options)


def test_missing_core_title_or_bad_source_cannot_bypass_duplicate_detection():
    for field, value in [('thesis_title', ''), ('source_sha256', 'wrong')]:
        rows = independent()
        rows[0][field] = value
        with pytest.raises(ValueError, match='invalid_' + field):
            make_grouped_split(rows)
