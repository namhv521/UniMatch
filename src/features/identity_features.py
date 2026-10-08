import numpy as np


def normalized_capacity_features(loads: np.ndarray, quotas: np.ndarray) -> np.ndarray:
    if loads.shape != quotas.shape or np.any(quotas <= 0):
        raise ValueError("loads and positive quotas must have identical shapes")
    return np.column_stack(((quotas - loads) / quotas, loads / quotas))
