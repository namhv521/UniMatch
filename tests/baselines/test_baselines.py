import numpy as np

from src.baselines.greedy import greedy_assignment
from src.baselines.hungarian import hungarian_assignment
from src.baselines.random import random_assignment


def _loads(assignments, n_advisors):
    return np.bincount(assignments, minlength=n_advisors)


def test_random_is_seeded_and_capacity_feasible():
    capacities = np.array([1, 2])

    first = random_assignment(3, capacities, seed=42)
    second = random_assignment(3, capacities, seed=42)

    np.testing.assert_array_equal(first, second)
    assert np.all(_loads(first, 2) <= capacities)


def test_greedy_picks_best_remaining_advisor():
    scores = np.array([[0.9, 0.8], [0.95, 0.1]])

    assignments = greedy_assignment(scores, capacities=np.array([1, 1]))

    np.testing.assert_array_equal(assignments, [0, 1])


def test_hungarian_expands_capacity_slots_for_global_optimum():
    scores = np.array([[0.9, 0.8], [0.85, 0.1]])

    assignments = hungarian_assignment(scores, capacities=np.array([1, 1]))

    np.testing.assert_array_equal(assignments, [1, 0])
    assert scores[np.arange(2), assignments].sum() == 1.65


def test_all_baselines_reject_insufficient_capacity():
    scores = np.array([[0.9], [0.8]])
    for call in (
        lambda: random_assignment(2, np.array([1]), seed=1),
        lambda: greedy_assignment(scores, np.array([1])),
        lambda: hungarian_assignment(scores, np.array([1])),
    ):
        try:
            call()
        except ValueError as error:
            assert "insufficient capacity" in str(error)
        else:
            raise AssertionError("expected insufficient capacity rejection")
