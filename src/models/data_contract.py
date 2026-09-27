"""Numerical contract shared by solvers, training and inference."""
import numpy as np


def validate_matching_data(scores, quotas):
    scores = np.asarray(scores, dtype=np.float64)
    quota_values = np.asarray(quotas, dtype=np.float64)
    if scores.ndim != 2 or min(scores.shape) == 0:
        raise ValueError('Compatibility must be a nonempty N by M matrix')
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError('Compatibility must be finite and in [0, 1]')
    if quota_values.shape != (scores.shape[1],):
        raise ValueError('One quota is required per advisor')
    if (not np.isfinite(quota_values).all() or np.any(quota_values < 0)
            or np.any(quota_values != np.floor(quota_values))):
        raise ValueError('Quotas must be nonnegative integers')
    # Larger quotas are equivalent to N slots and needlessly expand Hungarian matrices.
    quotas = np.minimum(quota_values, scores.shape[0]).astype(np.int64)
    if quotas.sum() < len(scores):
        raise ValueError('Insufficient capacity for cohort')
    return scores, quotas
