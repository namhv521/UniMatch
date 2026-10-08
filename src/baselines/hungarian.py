from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


def hungarian_assignment(scores, capacities) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    capacities = np.asarray(capacities, dtype=int)
    if scores.ndim != 2 or capacities.shape != (scores.shape[1],):
        raise ValueError("scores and capacities have incompatible shapes")
    if capacities.sum() < scores.shape[0]:
        raise ValueError("insufficient capacity")
    slot_advisors = np.repeat(np.arange(capacities.size), capacities)
    students, slots = linear_sum_assignment(-scores[:, slot_advisors])
    assignments = np.empty(scores.shape[0], dtype=int)
    assignments[students] = slot_advisors[slots]
    return assignments
