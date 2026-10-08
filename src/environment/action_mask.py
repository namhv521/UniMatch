from __future__ import annotations

import numpy as np


def feasible_action_mask(loads: np.ndarray, capacities: np.ndarray) -> np.ndarray:
    loads = np.asarray(loads)
    capacities = np.asarray(capacities)
    if loads.shape != capacities.shape:
        raise ValueError("loads and capacities must have the same shape")
    return loads < capacities
