"""Capacity-aware student-proposing stable matching."""
from .classical import allocate


def spa(scores, quotas):
    return allocate(scores, quotas, 'spa')
