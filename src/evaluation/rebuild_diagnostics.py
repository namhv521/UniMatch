"""Private feature diagnostics; these are never coordinator-approved allocations."""
import time

import numpy as np
from scipy.optimize import linear_sum_assignment


def _validate(scores, available, students, advisors):
    scores, available = np.asarray(scores), np.asarray(available)
    if (scores.shape != (len(students), len(advisors)) or available.shape != scores.shape
            or available.dtype != np.bool_ or not np.issubdtype(scores.dtype, np.number)
            or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any()
            or len(set(students)) != len(students) or len(set(advisors)) != len(advisors)
            or any(not isinstance(key, str) or not key.strip() for key in [*students, *advisors])):
        raise ValueError('invalid_feature_matrix_or_index')
    return scores, available


def rank_matrix(scores, available, students, advisors):
    scores, available = _validate(scores, available, students, advisors)
    return {student: [advisors[j] for j in sorted(np.flatnonzero(available[i]),
                    key=lambda j: (-float(scores[i, j]), advisors[j]))] for i, student in enumerate(students)}


def diagnostic_hungarian(scores, available, students, advisors):
    scores, available = _validate(scores, available, students, advisors)
    if not students or not advisors:
        raise ValueError('nonempty_diagnostic_population_required')
    started = time.perf_counter()
    q, r = divmod(len(students), len(advisors))
    capacities = [q + (i < r) for i in range(len(advisors))]
    slots = np.repeat(np.arange(len(advisors)), capacities)
    base = {'scope': 'research_only_profile_catalog_balanced_slots',
            'supervisory_eligibility_confirmed': False,
            'roster_policy': 'All supplied profile candidates; not a coordinator-selected semester roster.',
            'quota_policy': 'Diagnostic divmod slots in the recorded advisor order; not institutional capacity.',
            'advisor_order': list(advisors), 'capacities': dict(zip(advisors, map(int, capacities))),
            'objective_comparison_scope': 'Within each experiment score definition only; cross-experiment score scales differ.'}
    try:
        rows, columns = linear_sum_assignment(np.where(available[:, slots], -scores[:, slots], np.inf))
    except ValueError:
        return {**base, 'status': 'infeasible', 'reason': 'FEATURE_AVAILABILITY_CONFLICT',
                'coverage': 0.0, 'assignments': [], 'objective': None,
                'elapsed_seconds': time.perf_counter()-started}
    assignments = [{'student_id': students[i], 'advisor_id': advisors[slots[j]], 'score': float(scores[i, slots[j]])}
                   for i, j in zip(rows, columns)]
    loads = {advisor: sum(row['advisor_id'] == advisor for row in assignments) for advisor in advisors}
    violations = sum(loads[a] > capacities[j] for j, a in enumerate(advisors))
    return {**base, 'status': 'feasible', 'assignments': assignments, 'loads': loads,
            'coverage': len(assignments)/len(students), 'constraint_violations': int(violations),
            'objective': sum(row['score'] for row in assignments),
            'mean_compatibility': sum(row['score'] for row in assignments)/len(assignments),
            'elapsed_seconds': time.perf_counter()-started}


def summarize_matrix(scores, available):
    values = scores[available]
    return {'shape': list(scores.shape), 'dtype': str(scores.dtype),
            'observed_pairs': int(available.sum()), 'unavailable_pairs': int((~available).sum()),
            'pair_coverage': float(available.mean()) if available.size else 0.0,
            'students_without_candidates': int((~available.any(axis=1)).sum()),
            'advisors_without_candidates': int((~available.any(axis=0)).sum()),
            'observed_distribution': {key: float(value) for key, value in
                zip(('min', 'p25', 'median', 'p75', 'max'), np.quantile(values, [0, .25, .5, .75, 1]))} if values.size else None,
            'missing_policy': 'Numeric zero in storage is observed only where the availability mask is true.'}
