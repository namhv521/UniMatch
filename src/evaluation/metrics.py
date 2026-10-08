from __future__ import annotations

import numpy as np


def _assignments(values, *, n_advisors=None, allow_unassigned=False):
    result = np.asarray(values, dtype=int)
    if result.ndim != 1:
        raise ValueError("assignments must be a vector")
    minimum = -1 if allow_unassigned else 0
    if np.any(result < minimum) or (n_advisors is not None and np.any(result >= n_advisors)):
        raise ValueError("assignments must contain a valid advisor index")
    return result


def mean_compatibility(scores, assignments) -> float:
    scores = np.asarray(scores, dtype=float)
    assigned = _assignments(assignments, n_advisors=scores.shape[1])
    if scores.ndim != 2 or scores.shape[0] != assigned.size or assigned.size == 0:
        raise ValueError("scores and assignments must have compatible non-empty shapes")
    return float(scores[np.arange(assigned.size), assigned].mean())


def quota_violations(assignments, capacities) -> int:
    capacities = np.asarray(capacities, dtype=int)
    assigned = _assignments(assignments, n_advisors=capacities.size)
    loads = np.bincount(assigned, minlength=capacities.size)
    return int(np.maximum(loads - capacities, 0).sum())


def count_invalid_proposals(invalid_flags) -> int:
    return int(np.count_nonzero(np.asarray(invalid_flags, dtype=bool)))


def load_variance(assignments, n_advisors: int) -> float:
    assigned = _assignments(assignments, n_advisors=n_advisors)
    if assigned.size == 0:
        raise ValueError("at least one assignment is required")
    return float(np.var(np.bincount(assigned, minlength=n_advisors)))


def historical_top1_accuracy(assignments, historical, *, n_advisors: int):
    assigned = _assignments(assignments, n_advisors=n_advisors)
    reference = _assignments(historical, n_advisors=n_advisors, allow_unassigned=True)
    if assigned.shape != reference.shape:
        raise ValueError("assignments must have the same shape")
    known = reference >= 0
    return float(np.mean(assigned[known] == reference[known])) if np.any(known) else None


def theoretical_optimality_ratio(score: float, optimal_score: float):
    if score < 0 or optimal_score < 0:
        raise ValueError("scores must be non-negative")
    return None if optimal_score == 0 else score / optimal_score


def assignment_coverage(assignments) -> float:
    assigned = _assignments(assignments, allow_unassigned=True)
    if assigned.size == 0:
        raise ValueError("at least one assignment is required")
    return float(np.mean(assigned >= 0))


def assignment_stability(assignments, reference) -> float:
    assigned = np.asarray(assignments)
    baseline = np.asarray(reference)
    if assigned.shape != baseline.shape:
        raise ValueError("assignments must have the same shape")
    if assigned.ndim != 1 or assigned.size == 0:
        raise ValueError("assignments must be non-empty vectors")
    return float(np.mean(assigned == baseline))
