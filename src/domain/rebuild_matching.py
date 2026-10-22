"""Explicit operator constraints and globally safe masks for versioned matching."""
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np
from scipy.optimize import linear_sum_assignment


def _ids(values, name):
    values = tuple(values)
    if any(not isinstance(x, str) or not x.strip() or x != x.strip() for x in values) or len(set(values)) != len(values):
        raise ValueError('invalid_' + name)
    return values


def _array(value, shape, kind, dtype, name):
    array = np.asarray(value)
    if array.shape != shape or array.dtype.kind not in kind:
        raise ValueError('invalid_' + name)
    array = array.astype(dtype, copy=True)
    if array.dtype.kind == 'f' and not np.isfinite(array).all():
        raise ValueError('nonfinite_' + name)
    return array


def _readonly(array):
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class AllocationProblem:
    scores: np.ndarray
    available: np.ndarray
    student_ids: tuple
    advisor_ids: tuple
    capacities: np.ndarray
    eligible: np.ndarray
    present: np.ndarray
    fixed_assignments: dict = field(default_factory=dict)
    student_features: np.ndarray | None = None
    student_feature_known: np.ndarray | None = None
    preferences: np.ndarray | None = None
    preference_known: np.ndarray | None = None
    preference_weight: float = .1
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        student_ids, advisor_ids = _ids(self.student_ids, 'student_ids'), _ids(self.advisor_ids, 'advisor_ids')
        n, m = len(student_ids), len(advisor_ids)
        if not m:
            raise ValueError('empty_advisor_registry')
        scores = _array(self.scores, (n, m), 'f', np.float64, 'scores')
        available = _array(self.available, (n, m), 'b', bool, 'available')
        eligible = _array(self.eligible, (n, m), 'b', bool, 'eligible')
        present = _array(self.present, (m,), 'b', bool, 'present')
        capacities = _array(self.capacities, (m,), 'iu', np.int64, 'capacities')
        if (scores < 0).any() or (scores > 1).any() or (capacities < 0).any():
            raise ValueError('invalid_score_or_capacity_range')
        if (type(self.preference_weight) not in (int, float) or not np.isfinite(self.preference_weight)
                or self.preference_weight < 0):
            raise ValueError('invalid_preference_weight')
        preferences = (_array(self.preferences, (n, m), 'f', np.float64, 'preferences')
                       if self.preferences is not None else np.zeros((n, m), np.float64))
        preference_known = (_array(self.preference_known, (n, m), 'b', bool, 'preference_known')
                            if self.preference_known is not None else np.zeros((n, m), bool))
        if (preferences < 0).any() or (preferences > 1).any():
            raise ValueError('invalid_preference_range')
        if self.preferences is None and preference_known.any():
            raise ValueError('known_preference_without_value')
        features = np.empty((n, 0), np.float32) if self.student_features is None else np.asarray(self.student_features)
        if features.ndim != 2 or features.shape[0] != n:
            raise ValueError('invalid_student_features')
        features = _array(features, features.shape, 'f', np.float32, 'student_features')
        feature_known = (_array(self.student_feature_known, features.shape, 'b', bool, 'student_feature_known')
                         if self.student_feature_known is not None else np.zeros(features.shape, bool))
        if self.student_features is None and feature_known.any():
            raise ValueError('known_feature_without_value')
        if (not isinstance(self.fixed_assignments, dict)
                or any(s not in student_ids or a not in advisor_ids for s, a in self.fixed_assignments.items())):
            raise ValueError('invalid_fixed_assignments')
        if not isinstance(self.metadata, dict):
            raise ValueError('invalid_metadata')
        scores[~available], preferences[~preference_known], features[~feature_known] = 0, 0, 0
        for name, value in {'scores': scores, 'available': available, 'eligible': eligible,
                            'present': present, 'capacities': capacities,
                            'preferences': preferences, 'preference_known': preference_known}.items():
            object.__setattr__(self, name, _readonly(value))
        object.__setattr__(self, 'student_ids', student_ids)
        object.__setattr__(self, 'advisor_ids', advisor_ids)
        object.__setattr__(self, 'student_features', _readonly(features))
        object.__setattr__(self, 'student_feature_known', _readonly(feature_known))
        object.__setattr__(self, 'fixed_assignments', MappingProxyType(dict(self.fixed_assignments)))
        object.__setattr__(self, 'metadata', deepcopy(self.metadata))

    @property
    def allowed(self):
        allowed = self.available & self.eligible & self.present[None, :]
        for student, advisor in self.fixed_assignments.items():
            i, j = self.student_ids.index(student), self.advisor_ids.index(advisor)
            allowed[i, :j] = False
            allowed[i, j+1:] = False
        return allowed

    @property
    def utility(self):
        return self.scores + self.preference_weight * self.preferences


def equal_quotas(n, advisor_ids, selected_advisor_ids):
    registry = _ids(advisor_ids, 'advisor_ids')
    selected = _ids(selected_advisor_ids, 'selected_advisor_ids')
    if not isinstance(n, (int, np.integer)) or isinstance(n, (bool, np.bool_)) or n < 0 or not selected or not set(selected) <= set(registry):
        raise ValueError('invalid_equal_quota_inputs')
    quotient, remainder = divmod(n, len(selected))
    values = {key: quotient + (position < remainder) for position, key in enumerate(sorted(selected))}
    return np.array([values.get(key, 0) for key in registry], np.int64)


def _state(problem, remaining_students=None, remaining_capacities=None):
    raw = list(range(len(problem.student_ids))) if remaining_students is None else list(remaining_students)
    students = []
    for key in raw:
        if isinstance(key, str) and key in problem.student_ids:
            students.append(problem.student_ids.index(key))
        elif isinstance(key, (int, np.integer)) and not isinstance(key, (bool, np.bool_)) and 0 <= key < len(problem.student_ids):
            students.append(int(key))
        else:
            raise ValueError('invalid_remaining_students')
    if len(set(students)) != len(students):
        raise ValueError('duplicate_remaining_students')
    capacities = problem.capacities.copy() if remaining_capacities is None else _array(
        remaining_capacities, problem.capacities.shape, 'iu', np.int64, 'remaining_capacities')
    if (capacities < 0).any() or (capacities > problem.capacities).any():
        raise ValueError('invalid_remaining_capacities')
    return students, capacities


def feasible(problem, *, remaining_students=None, remaining_capacities=None):
    """Exact Hall feasibility through slot expansion; fixed future rows stay restricted."""
    students, capacities = _state(problem, remaining_students, remaining_capacities)
    if not students:
        return True
    allowed = problem.allowed[students] & (capacities > 0)
    if int(capacities.sum()) < len(students) or not allowed.any(axis=1).all():
        return False
    # Dense graphs require no slot expansion and occur frequently in research cohorts.
    active = capacities > 0
    if allowed[:, active].all():
        return True
    slots = np.repeat(np.arange(len(capacities)), np.minimum(capacities, len(students)))
    rows, columns = linear_sum_assignment(~allowed[:, slots])
    return len(rows) == len(students) and bool(allowed[rows, slots[columns]].all())


def action_mask(problem, remaining_students, remaining_capacities):
    students, capacities = _state(problem, remaining_students, remaining_capacities)
    mask = np.zeros(len(problem.advisor_ids), bool)
    if not students:
        return mask
    allowed = problem.allowed
    active = capacities > 0
    candidates = allowed[students[0]] & active
    if (int(capacities.sum()) >= len(students)
            and allowed[students[1:]][:, active].all()):
        return candidates.copy()
    for advisor in np.flatnonzero(candidates):
        residual = capacities.copy()
        residual[advisor] -= 1
        mask[advisor] = feasible(problem, remaining_students=students[1:], remaining_capacities=residual)
    return mask


def validate_assignments(problem, assignments):
    """Validate identity, hard constraints and any supplied scores against the problem."""
    violations, seen = [], set()
    loads = np.zeros(len(problem.advisor_ids), np.int64)
    allowed = problem.allowed
    for number, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            violations.append({'row': number, 'code': 'invalid_assignment'})
            continue
        student, advisor = assignment.get('student_id'), assignment.get('advisor_id')
        if student not in problem.student_ids or advisor not in problem.advisor_ids:
            violations.append({'row': number, 'code': 'unknown_identity'})
            continue
        i, j = problem.student_ids.index(student), problem.advisor_ids.index(advisor)
        if student in seen:
            violations.append({'row': number, 'code': 'duplicate_student'})
        seen.add(student)
        loads[j] += 1
        if not allowed[i, j]:
            violations.append({'row': number, 'code': 'forbidden_pair'})
        for field_name, expected in [('score', float(problem.scores[i, j])),
                                     ('preference', float(problem.preferences[i, j])),
                                     ('preference_known', bool(problem.preference_known[i, j]))]:
            if field_name in assignment:
                value = assignment[field_name]
                valid = (type(value) is bool and value == expected if field_name == 'preference_known'
                         else type(value) in (int, float) and np.isfinite(value) and np.isclose(value, expected, atol=1e-12, rtol=0))
                if not valid:
                    violations.append({'row': number, 'code': 'incorrect_' + field_name})
    for advisor in np.flatnonzero(loads > problem.capacities):
        violations.append({'advisor_id': problem.advisor_ids[advisor], 'code': 'capacity_exceeded'})
    coverage = len(seen)/len(problem.student_ids) if problem.student_ids else 1.
    if len(seen) != len(problem.student_ids):
        violations.append({'code': 'incomplete_coverage'})
    return {'valid': not violations, 'coverage': coverage, 'violations': violations}
