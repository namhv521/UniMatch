from itertools import product

import numpy as np
import pytest


def test_exact_matches_exhaustive_search_and_baselines_respect_quota():
    from src.baselines.classical import allocate
    scores = np.array([[.9, .8], [.95, .1], [.4, .6]])
    quota = np.array([1, 2])
    optimum = max(sum(scores[i, a] for i, a in enumerate(assignment))
                  for assignment in product(range(2), repeat=3)
                  if np.all(np.bincount(assignment, minlength=2) <= quota))
    for strategy in ['random', 'greedy', 'spa', 'exact']:
        result = allocate(scores, quota, strategy, seed=42)
        assert len(result) == 3
        assert np.all(np.bincount(result, minlength=2) <= quota)
        value = scores[np.arange(3), result].sum()
        assert value <= optimum + 1e-8
        if strategy == 'exact':
            assert value == pytest.approx(optimum)


def test_spa_has_no_blocking_pairs_with_strict_scores():
    from src.baselines.classical import allocate
    scores = np.random.default_rng(42).random((7, 3))
    quota = np.array([3, 2, 2])
    assignment = allocate(scores, quota, 'spa')
    for student, current in enumerate(assignment):
        for advisor in range(3):
            if scores[student, advisor] > scores[student, current]:
                held = np.flatnonzero(assignment == advisor)
                assert len(held) == quota[advisor]
                assert np.all(scores[held, advisor] >= scores[student, advisor])


def test_contract_rejects_bad_scores_and_capacity():
    from src.baselines.classical import allocate
    for scores, quotas in [([[float('nan')]], [1]), ([[1]], [0]), ([[1]], [.5]),
                            ([[2]], [1]), ([[.5]], [-1])]:
        with pytest.raises(ValueError):
            allocate(scores, quotas)
