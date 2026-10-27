import copy
import math

import pytest

from src.evaluation.rebuild_ranking import (
    calibrate_e4,
    hybrid_score,
    ranking_metrics,
    validate_pair_labels,
)


SNAPSHOT = 'a' * 64
STUDENTS = {'s1': 'b' * 64, 's2': 'c' * 64}
ADVISORS = {'a1': 'd' * 64, 'a2': 'e' * 64, 'a3': 'f' * 64}


def label(student, advisor, grade):
    return {'student_id': student, 'advisor_id': advisor,
            'student_record_sha256': STUDENTS[student], 'advisor_record_sha256': ADVISORS[advisor],
            'snapshot_sha256': SNAPSHOT, 'grade': grade, 'attribution': 'agent_advisory',
            'reviewer': 'agent:test-fixture'}


def test_known_ndcg_and_mrr_use_actual_ranks():
    labels = [label('s1', 'a1', 3), label('s1', 'a2', 0), label('s1', 'a3', 2)]
    result = ranking_metrics({'s1': ['a2', 'a3', 'a1']}, labels, k=5)
    expected = (3 / math.log2(3) + 7 / math.log2(4)) / (7 + 3 / math.log2(3))
    assert result['ndcg_at_5'] == pytest.approx(expected)
    assert result['mrr_at_5'] == 0.5
    assert result['judgment_coverage'] == 1
    assert result['evaluated_queries'] == 1


def test_uncertain_or_unread_pairs_are_not_zero_relevance():
    labels = [label('s1', 'a1', 3), label('s1', 'a2', 'uncertain')]
    result = ranking_metrics({'s1': ['a2', 'a1', 'a3']}, labels)
    assert result['ndcg_at_5'] is None
    assert result['mrr_at_5'] is None
    assert result['evaluated_queries'] == 0
    assert result['judgment_coverage'] == pytest.approx(1 / 3)
    assert result['unknown_pairs'] == 2
    assert result['per_query']['s1']['status'] == 'insufficient_judgments'


def test_zero_grade_is_known_and_distinct_from_unknown():
    result = ranking_metrics({'s1': ['a1', 'a2']}, [label('s1', 'a1', 0), label('s1', 'a2', 0)])
    assert result['ndcg_at_5'] == 0
    assert result['mrr_at_5'] == 0
    assert result['judgment_coverage'] == 1


def test_pair_labels_are_bound_to_exact_snapshot_and_records():
    labels = [label('s1', 'a1', 3), label('s1', 'a2', 'uncertain')]
    assert validate_pair_labels(labels, student_hashes=STUDENTS, advisor_hashes=ADVISORS,
                                snapshot_sha256=SNAPSHOT) == labels
    for field in ('student_record_sha256', 'advisor_record_sha256', 'snapshot_sha256'):
        changed = copy.deepcopy(labels)
        changed[0][field] = '0' * 64
        with pytest.raises(ValueError):
            validate_pair_labels(changed, student_hashes=STUDENTS, advisor_hashes=ADVISORS,
                                 snapshot_sha256=SNAPSHOT)
    with pytest.raises(ValueError):
        validate_pair_labels(labels + [labels[0]], student_hashes=STUDENTS,
                             advisor_hashes=ADVISORS, snapshot_sha256=SNAPSHOT)


@pytest.mark.parametrize('grade', [-1, 4, True, 2.5, None, '2', float('nan')])
def test_invalid_grades_are_rejected(grade):
    with pytest.raises(ValueError):
        validate_pair_labels([label('s1', 'a1', grade)], student_hashes=STUDENTS,
                             advisor_hashes=ADVISORS, snapshot_sha256=SNAPSHOT)


def test_owner_ratified_attribution_requires_approval_evidence():
    row = {**label('s1', 'a1', 2), 'attribution': 'owner_ratified', 'reviewer': 'owner:test-fixture'}
    with pytest.raises(ValueError):
        validate_pair_labels([row], student_hashes=STUDENTS, advisor_hashes=ADVISORS,
                             snapshot_sha256=SNAPSHOT)
    row['approval_evidence_sha256'] = '1' * 64
    assert validate_pair_labels([row], student_hashes=STUDENTS, advisor_hashes=ADVISORS,
                                snapshot_sha256=SNAPSHOT)[0]['attribution'] == 'owner_ratified'


def test_hybrid_missing_components_renormalize_only_available_weights():
    assert hybrid_score({'E1': 0.2, 'E2': None, 'E3': 0.8}, {'E1': 0.5, 'E2': 0.25, 'E3': 0.25}) == pytest.approx(0.4)
    assert hybrid_score({'E1': None, 'E2': None, 'E3': None}, {'E1': 1, 'E2': 0, 'E3': 0}) is None
    assert hybrid_score({'E1': None, 'E2': 0.8, 'E3': 0.1}, {'E1': 1, 'E2': 0, 'E3': 0}) is None
    for weights in ({'E1': -0.2, 'E2': 0.6, 'E3': 0.6}, {'E1': 1, 'E2': 1, 'E3': 1}):
        with pytest.raises(ValueError):
            hybrid_score({'E1': 0.2, 'E2': 0.3, 'E3': 0.4}, weights)


def test_calibration_fits_only_validation_and_heldout_cannot_change_weights():
    components = {'E1': {'s1': {'a1': 0.9, 'a2': 0.1}, 's2': {'a1': 0, 'a2': 1}},
                  'E2': {'s1': {'a1': 0.1, 'a2': 0.9}, 's2': {'a1': 0, 'a2': 1}},
                  'E3': {'s1': {'a1': 0.1, 'a2': 0.9}, 's2': {'a1': 0, 'a2': 1}}}
    labels = [label('s1', 'a1', 3), label('s1', 'a2', 0), label('s2', 'a1', 3), label('s2', 'a2', 0)]
    splits = {'s1': 'validation', 's2': 'test'}
    first = calibrate_e4(components, labels, splits, step=0.25)
    modified_labels = copy.deepcopy(labels)
    modified_labels[2]['grade'], modified_labels[3]['grade'] = 0, 3
    modified_components = copy.deepcopy(components)
    for name in modified_components:
        modified_components[name]['s2'] = {'a1': -100, 'a2': float('nan')}
    second = calibrate_e4(modified_components, modified_labels, splits, step=0.25)
    assert first['status'] == 'calibrated_validation_only'
    assert first['weights'] == second['weights']
    assert first['ndcg_at_5'] == 1
    assert first['calibration_students'] == ['s1']
    assert first['labels_used'] == 2
    assert len(first['grid_results']) == 15


def test_no_validation_judgments_is_explicitly_uncalibrated():
    components = {name: {'s1': {'a1': 0.8}} for name in ['E1', 'E2', 'E3']}
    result = calibrate_e4(components, [label('s1', 'a1', 3)], {'s1': 'train'})
    assert result['status'] == 'insufficient_validation_judgments'
    assert result['weights'] is None


def test_predeclared_minimum_text_weight_excludes_pure_missing_tag_grids():
    components = {'E1': {'s1': {'a1': 0.9, 'a2': 0.1}},
                  'E2': {'s1': {'a1': None, 'a2': None}},
                  'E3': {'s1': {'a1': None, 'a2': None}}}
    labels = [label('s1', 'a1', 3), label('s1', 'a2', 0)]
    result = calibrate_e4(components, labels, {'s1': 'validation'}, min_text_weight=0.25)
    assert result['status'] == 'calibrated_validation_only'
    assert result['min_text_weight'] == 0.25
    assert result['candidate_grid_count'] == len(result['grid_results']) == 10
    assert all(grid['weights']['E1'] >= 0.25 for grid in result['grid_results'])
    pure_text = calibrate_e4(components, labels, {'s1': 'validation'}, min_text_weight=1)
    assert len(pure_text['grid_results']) == 1
    assert pure_text['weights'] == {'E1': 1, 'E2': 0, 'E3': 0}


@pytest.mark.parametrize('minimum', [-0.1, 1.1, True, float('nan'), float('inf')])
def test_invalid_minimum_text_weight_is_rejected(minimum):
    with pytest.raises(ValueError):
        calibrate_e4({name: {} for name in ['E1', 'E2', 'E3']}, [], {}, min_text_weight=minimum)
