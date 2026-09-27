"""Maximum total compatibility; no fairness objective is implied."""
from .classical import allocate


def exact_hungarian(scores, quotas):
    return allocate(scores, quotas, 'exact')
