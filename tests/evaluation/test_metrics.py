import numpy as np
import pytest

from src.evaluation.metrics import (
    assignment_coverage,
    assignment_stability,
    count_invalid_proposals,
    historical_top1_accuracy,
    load_variance,
    mean_compatibility,
    quota_violations,
    theoretical_optimality_ratio,
)


def test_matching_metrics_have_hand_calculated_values():
    scores = np.array([[0.9, 0.4], [0.2, 0.8], [0.7, 0.3]])
    assignments = np.array([0, 1, 0])

    assert mean_compatibility(scores, assignments) == pytest.approx(0.8)
    assert quota_violations(assignments, np.array([1, 2])) == 1
    assert load_variance(assignments, n_advisors=2) == pytest.approx(0.25)


def test_proposal_coverage_and_stability_metrics_have_known_values():
    assert count_invalid_proposals([False, True, False, True]) == 2
    assert assignment_coverage([0, -1, 1]) == pytest.approx(2 / 3)
    assert assignment_stability([0, 1, 0], [0, 0, 0]) == pytest.approx(2 / 3)


def test_reference_and_optimality_metrics_have_known_values():
    assignments = np.array([0, 1, 0])

    assert historical_top1_accuracy(assignments, [0, -1, 1], n_advisors=2) == pytest.approx(0.5)
    assert historical_top1_accuracy(assignments, [-1, -1, -1], n_advisors=2) is None
    assert theoretical_optimality_ratio(2.4, 2.5) == pytest.approx(0.96)
    assert theoretical_optimality_ratio(0.0, 0.0) is None


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: mean_compatibility([[0.5]], [-1]), "valid advisor index"),
        (lambda: quota_violations([2], [1, 1]), "valid advisor index"),
        (lambda: load_variance([], 2), "at least one assignment"),
        (lambda: assignment_stability([0], [0, 1]), "same shape"),
        (lambda: theoretical_optimality_ratio(1.0, -1.0), "non-negative"),
    ],
)
def test_metrics_reject_invalid_inputs(call, message):
    with pytest.raises(ValueError, match=message):
        call()
