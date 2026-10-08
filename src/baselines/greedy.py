from __future__ import annotations

import numpy as np


def greedy_assignment(scores, capacities) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    capacities = np.asarray(capacities, dtype=int)
    if scores.ndim != 2 or capacities.shape != (scores.shape[1],):
        raise ValueError("scores and capacities have incompatible shapes")
    if capacities.sum() < scores.shape[0]:
        raise ValueError("insufficient capacity")
    remaining = capacities.copy()
    assignments = np.empty(scores.shape[0], dtype=int)
    for student, row in enumerate(scores):
        feasible = np.flatnonzero(remaining > 0)
        advisor = feasible[np.argmax(row[feasible])]
        assignments[student] = advisor
        remaining[advisor] -= 1
    return assignments
