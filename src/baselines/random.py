from __future__ import annotations

import numpy as np


def random_assignment(n_students: int, capacities, *, seed: int) -> np.ndarray:
    capacities = np.asarray(capacities, dtype=int)
    if capacities.ndim != 1 or np.any(capacities < 0):
        raise ValueError("capacities must be a non-negative vector")
    if capacities.sum() < n_students:
        raise ValueError("insufficient capacity")
    slots = np.repeat(np.arange(capacities.size), capacities)
    return np.random.default_rng(seed).choice(slots, size=n_students, replace=False)
