import numpy as np
import pytest


def test_rankings_do_not_turn_missing_scores_into_real_zero_matches():
    from src.evaluation.rebuild_diagnostics import rank_matrix
    scores = np.array([[0.0, 0.8, 0.0]])
    available = np.array([[True, True, False]])
    assert rank_matrix(scores, available, ['student'], ['b', 'a', 'c']) == {'student': ['a', 'b']}
    with pytest.raises(ValueError):
        rank_matrix(scores, available, ['student'], ['a', 'a', 'c'])


def test_diagnostic_hungarian_has_exact_constraints_and_never_publishes_allocation():
    from src.evaluation.rebuild_diagnostics import diagnostic_hungarian
    scores = np.array([[.9, .8], [.85, .1]])
    result = diagnostic_hungarian(scores, np.ones((2, 2), dtype=bool), ['s1', 's2'], ['a1', 'a2'])
    assert result['status'] == 'feasible'
    assert result['objective'] == pytest.approx(1.65)
    assert result['coverage'] == 1 and result['constraint_violations'] == 0
    assert result['scope'] == 'research_only_profile_catalog_balanced_slots'
    assert not result['supervisory_eligibility_confirmed']
    assert {r['student_id'] for r in result['assignments']} == {'s1', 's2'}


def test_unavailable_feature_pairs_produce_explicit_infeasibility():
    from src.evaluation.rebuild_diagnostics import diagnostic_hungarian
    result = diagnostic_hungarian(np.ones((2, 2)), np.array([[True, False], [True, False]]),
                                  ['s1', 's2'], ['a1', 'a2'])
    assert result['status'] == 'infeasible' and result['assignments'] == []
    assert result['reason'] == 'FEATURE_AVAILABILITY_CONFLICT'


def test_diagnostics_validate_matrix_masks_and_shapes():
    from src.evaluation.rebuild_diagnostics import rank_matrix
    for scores, mask in [(np.array([[np.nan]]), np.array([[True]])),
                         (np.array([[1.1]]), np.array([[True]])),
                         (np.array([[.1]]), np.array([['false']])),
                         (np.array([[.1]]), np.array([[True, True]]))]:
        with pytest.raises(ValueError):
            rank_matrix(scores, mask, ['student'], ['advisor'])
