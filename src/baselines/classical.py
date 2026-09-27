"""Capacity constrained batch baselines; deterministic ties use input order."""
from collections import deque

import numpy as np
from scipy.optimize import linear_sum_assignment

from src.models.data_contract import validate_matching_data


def allocate(scores, quotas, strategy='exact', seed=42):
    scores, quotas = validate_matching_data(scores, quotas)
    n, m = scores.shape
    result = np.full(n, -1, dtype=np.int64)
    if strategy == 'exact':
        slots = np.repeat(np.arange(m), quotas)
        rows, columns = linear_sum_assignment(-scores[:, slots])
        result[rows] = slots[columns]
    elif strategy in ('random', 'greedy'):
        remaining = quotas.copy()
        rng = np.random.default_rng(seed)
        for student in range(n):
            feasible = np.flatnonzero(remaining > 0)
            advisor = (rng.choice(feasible) if strategy == 'random'
                       else feasible[np.argmax(scores[student, feasible])])
            result[student] = advisor
            remaining[advisor] -= 1
    elif strategy == 'spa':
        # Hospital/residents specialization: each advisor is one project pool.
        preferences = np.argsort(-scores, axis=1, kind='stable')
        next_choice = np.zeros(n, dtype=int)
        held = [[] for _ in range(m)]
        waiting = deque(range(n))
        while waiting:
            student = waiting.popleft()
            if next_choice[student] >= m:
                raise RuntimeError('No feasible advisor remains')
            advisor = int(preferences[student, next_choice[student]])
            next_choice[student] += 1
            held[advisor].append(student)
            held[advisor].sort(key=lambda i: (-scores[i, advisor], i))
            if len(held[advisor]) > quotas[advisor]:
                waiting.append(held[advisor].pop())
        for advisor, students in enumerate(held):
            result[students] = advisor
    else:
        raise ValueError(f'Unknown strategy: {strategy}')
    return result
