from __future__ import annotations

import numpy as np


def matching_reward(
    compatibility: float,
    loads_before,
    loads_after,
    *,
    invalid: bool = False,
    compatibility_weight: float = 1.0,
    fairness_weight: float = 0.15,
    invalid_penalty: float = 2.0,
) -> float:
    before = np.asarray(loads_before, dtype=float)
    after = np.asarray(loads_after, dtype=float)
    if not 0.0 <= compatibility <= 1.0:
        raise ValueError("compatibility must be between 0 and 1")
    if before.shape != after.shape:
        raise ValueError("loads must have the same shape")
    if before.ndim != 1 or before.size == 0:
        raise ValueError("loads must be non-empty vectors")
    if np.any(before < 0) or np.any(after < 0):
        raise ValueError("loads must be non-negative")
    if min(compatibility_weight, fairness_weight, invalid_penalty) < 0:
        raise ValueError("weights must be non-negative")
    fairness = float(np.var(before) - np.var(after))
    return compatibility_weight * compatibility + fairness_weight * fairness - invalid_penalty * bool(invalid)
