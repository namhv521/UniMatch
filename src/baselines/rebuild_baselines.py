"""Hungarian, safe Greedy and safe Random under one explicit constraint contract."""
from time import perf_counter

import numpy as np
from scipy.optimize import linear_sum_assignment

from src.domain.rebuild_matching import action_mask, feasible, validate_assignments


def solve(problem, algorithm='hungarian', seed=42):
    if algorithm not in {'hungarian', 'greedy', 'random'} or type(seed) is not int:
        raise ValueError('invalid_baseline_configuration')
    start = perf_counter()
    n, m = problem.scores.shape
    metrics = {'objective': None, 'mean_compatibility': None, 'min_compatibility': None,
               'p10_compatibility': None, 'normalized_load_imbalance': None,
               'coverage': 0., 'constraint_violations': 0}
    if not feasible(problem):
        return {'status': 'infeasible', 'assignments': [], 'metrics': metrics,
                'elapsed_seconds': perf_counter() - start,
                'diagnostics': {'reason': 'no_complete_matching_under_capacity_eligibility_presence_availability_and_fixed_constraints'}}
    indices = []
    if algorithm == 'hungarian' and n:
        slots = np.repeat(np.arange(m), np.minimum(problem.capacities, n))
        allowed = problem.allowed[:, slots]
        costs = np.where(allowed, -problem.utility[:, slots], np.inf)
        rows, columns = linear_sum_assignment(costs)
        indices = sorted(zip(rows.tolist(), slots[columns].tolist()))
    elif n:
        random = np.random.default_rng(seed)
        capacities = problem.capacities.copy()
        for student in range(n):
            candidates = np.flatnonzero(action_mask(problem, range(student, n), capacities))
            if not len(candidates):
                raise RuntimeError('feasible_problem_stranded_by_safe_mask')
            if algorithm == 'random':
                advisor = int(random.choice(candidates))
            else:
                advisor = min(candidates, key=lambda j: (-problem.utility[student, j], problem.advisor_ids[j]))
            indices.append((student, advisor))
            capacities[advisor] -= 1
    assignments = [{'student_id': problem.student_ids[i], 'advisor_id': problem.advisor_ids[j],
                    'score': float(problem.scores[i, j]), 'preference': float(problem.preferences[i, j]),
                    'preference_known': bool(problem.preference_known[i, j])} for i, j in indices]
    validation = validate_assignments(problem, assignments)
    if not validation['valid']:
        raise RuntimeError('baseline_final_validation_failed')
    scores = np.array([problem.scores[i, j] for i, j in indices])
    loads = np.bincount([j for i, j in indices], minlength=m)
    active = problem.present & (problem.capacities > 0)
    utilization = loads[active]/problem.capacities[active]
    metrics.update(objective=float(sum(problem.utility[i, j] for i, j in indices)),
                   mean_compatibility=float(scores.mean()) if n else None,
                   min_compatibility=float(scores.min()) if n else None,
                   p10_compatibility=float(np.quantile(scores, .1)) if n else None,
                   normalized_load_imbalance=float(np.ptp(utilization)) if len(utilization) else 0.,
                   coverage=validation['coverage'], constraint_violations=len(validation['violations']))
    return {'status': 'feasible', 'assignments': assignments, 'metrics': metrics,
            'elapsed_seconds': perf_counter() - start,
            'diagnostics': {'algorithm': algorithm, 'seed': seed,
                            'objective': 'sum(score + preference_weight * observed_preference)',
                            'fairness': 'max(load/residual_capacity)-min(load/residual_capacity) over present positive-capacity advisors',
                            'existing_load': 'not_inferred; supplied_capacities_are_residual_slots'}}
