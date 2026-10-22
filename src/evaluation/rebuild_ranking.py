"""Evidence-bound advisory ranking metrics and validation-only hybrid calibration.

Relevance grades describe topic/profile fit, never observed supervision outcomes.
Unknown labels are excluded from judgments and never converted into grade zero.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from numbers import Real


COMPONENTS = ('E1', 'E2', 'E3')


def _sha256(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _grade(value):
    if value == 'uncertain':
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
        raise ValueError('invalid_relevance_grade')
    return value


def _label_index(labels):
    index = {}
    for label in labels:
        key = (label.get('student_id'), label.get('advisor_id'))
        if not all(isinstance(item, str) and item.strip() for item in key):
            raise ValueError('invalid_pair_identity')
        if key in index:
            raise ValueError('duplicate_pair_label')
        index[key] = _grade(label.get('grade'))
    return index


def validate_pair_labels(labels, *, student_hashes, advisor_hashes, snapshot_sha256):
    """Validate attribution and exact record/snapshot bindings; return copied rows.

    Owner approval evidence is a required reference, not an assertion that this
    module independently authenticates the owner's authorization. The caller
    must verify that reference against its approval ledger.
    """
    labels = list(labels)
    _label_index(labels)
    if not _sha256(snapshot_sha256):
        raise ValueError('invalid_snapshot_hash')
    for label in labels:
        student, advisor = label['student_id'], label['advisor_id']
        if student not in student_hashes or advisor not in advisor_hashes:
            raise ValueError('unknown_pair_identity')
        expected = {'student_record_sha256': student_hashes[student],
                    'advisor_record_sha256': advisor_hashes[advisor],
                    'snapshot_sha256': snapshot_sha256}
        if any(not _sha256(value) or label.get(key) != value for key, value in expected.items()):
            raise ValueError('pair_label_hash_mismatch')
        attribution = label.get('attribution')
        if attribution not in {'agent_advisory', 'owner_ratified'}:
            raise ValueError('invalid_label_attribution')
        if not isinstance(label.get('reviewer'), str) or not label['reviewer'].strip():
            raise ValueError('label_reviewer_required')
        if attribution == 'owner_ratified' and not _sha256(label.get('approval_evidence_sha256')):
            raise ValueError('owner_approval_evidence_required')
    return [dict(row) for row in labels]


def ranking_metrics(rankings, labels, *, k=5, relevant_grade=2):
    """Macro NDCG/MRR at actual ranks, conditional on fully judged top-k.

    IDCG uses the student's known judged pool, not assumed relevance of unseen
    advisors. A missing or uncertain top-k judgment makes that query's metrics
    unknown. Query and slot coverage expose the resulting evaluation limits.
    Exact hashes must first be checked with validate_pair_labels().
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError('invalid_ranking_cutoff')
    if isinstance(relevant_grade, bool) or not isinstance(relevant_grade, int) or not 0 <= relevant_grade <= 3:
        raise ValueError('invalid_relevant_grade')
    labels = list(labels)
    index = _label_index(labels)
    known_by_student = defaultdict(list)
    for (student, _), grade in index.items():
        if grade is not None:
            known_by_student[student].append(grade)
    per_query, slots, known_slots = {}, 0, 0
    for student, ordering in rankings.items():
        if not isinstance(student, str) or not student.strip() or not isinstance(ordering, (list, tuple)):
            raise ValueError('invalid_ranking')
        if any(not isinstance(advisor, str) or not advisor.strip() for advisor in ordering):
            raise ValueError('invalid_ranked_advisor')
        if len(set(ordering)) != len(ordering):
            raise ValueError('duplicate_ranked_advisor')
        top = list(ordering[:k])
        grades = [index.get((student, advisor)) for advisor in top]
        known = sum(grade is not None for grade in grades)
        slots += len(top)
        known_slots += known
        result = {'status': 'insufficient_judgments', 'ranked_top_k': top,
                  'known_top_k': known, 'unknown_top_k': len(top) - known,
                  f'ndcg_at_{k}': None, f'mrr_at_{k}': None}
        if top and known == len(top):
            dcg = sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))
            ideal = sorted(known_by_student[student], reverse=True)[:k]
            idcg = sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(ideal))
            reciprocal = next((1 / (rank + 1) for rank, grade in enumerate(grades) if grade >= relevant_grade), 0.0)
            result.update(status='evaluated', **{f'ndcg_at_{k}': dcg / idcg if idcg else 0.0,
                                                f'mrr_at_{k}': reciprocal})
        elif not top:
            result['status'] = 'no_ranked_candidates'
        per_query[student] = result
    evaluated = [row for row in per_query.values() if row['status'] == 'evaluated']
    return {f'ndcg_at_{k}': sum(r[f'ndcg_at_{k}'] for r in evaluated) / len(evaluated) if evaluated else None,
            f'mrr_at_{k}': sum(r[f'mrr_at_{k}'] for r in evaluated) / len(evaluated) if evaluated else None,
            'cutoff': k, 'relevant_grade': relevant_grade,
            'coverage': len(evaluated) / len(per_query) if per_query else 0.0,
            'judgment_coverage': known_slots / slots if slots else 0.0,
            'evaluated_queries': len(evaluated), 'query_count': len(per_query),
            'unknown_pairs': slots - known_slots, 'known_top_k_pairs': known_slots,
            'label_attributions': dict(Counter(r.get('attribution', 'unverified') for r in labels)),
            'metric_scope': 'Fully judged top-k; IDCG over known judged pool; unknown is not grade zero.',
            'per_query': per_query}


def _weights(weights):
    if set(weights) != set(COMPONENTS):
        raise ValueError('invalid_component_weights')
    if any(isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0
           for value in weights.values()) or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError('weights_must_be_nonnegative_convex')


def hybrid_score(scores, weights):
    """Renormalize convex weights over observed components; all missing is None."""
    _weights(weights)
    if set(scores) - set(COMPONENTS):
        raise ValueError('unknown_component')
    observed = {}
    for name in COMPONENTS:
        score = scores.get(name)
        if score is None:
            continue
        if isinstance(score, bool) or not isinstance(score, Real) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('invalid_component_score')
        observed[name] = score
    total = sum(weights[name] for name in observed)
    return sum(weights[name] * score for name, score in observed.items()) / total if total else None


def calibrate_e4(components, labels, student_splits, *, step=0.25, k=5, min_text_weight=0.0):
    """Fit E1/E2/E3 convex weights using validation judgments only.

    Components map component -> student -> advisor -> score or None. Training
    and test labels/scores are neither validated nor inspected by calibration.
    Every grid point is compared on identical, fully judged validation queries.
    """
    if set(components) != set(COMPONENTS):
        raise ValueError('expected_E1_E2_E3_components')
    if isinstance(step, bool) or not isinstance(step, Real) or not math.isfinite(step) or not 0 < step <= 1:
        raise ValueError('invalid_grid_step')
    divisions = round(1 / step)
    if not math.isclose(divisions * step, 1.0, abs_tol=1e-9):
        raise ValueError('grid_step_must_divide_one')
    if (isinstance(min_text_weight, bool) or not isinstance(min_text_weight, Real)
            or not math.isfinite(min_text_weight) or not 0 <= min_text_weight <= 1):
        raise ValueError('invalid_minimum_text_weight')
    # Filter before accessing grades, attribution, hashes or scores of holdouts.
    validation_labels = [row for row in labels if student_splits.get(row.get('student_id')) == 'validation']
    _label_index(validation_labels)
    students = sorted({row['student_id'] for row in validation_labels})
    base = {'status': 'insufficient_validation_judgments', 'weights': None,
            'calibration_students': students, 'labels_used': len(validation_labels),
            'calibration_split': 'validation', 'grid_step': float(step), 'grid_results': [],
            'min_text_weight': float(min_text_weight),
            'candidate_grid_count': sum(first / divisions >= min_text_weight
                                        for first in range(divisions + 1)
                                        for second in range(divisions - first + 1)),
            f'ndcg_at_{k}': None, f'mrr_at_{k}': None,
            'label_attributions': dict(Counter(r.get('attribution', 'unverified') for r in validation_labels)),
            'preference_input': 'not_used_no_confirmed_preferences',
            'metric_scope': 'Common fully judged validation queries; IDCG over known judged pool.'}
    if not students:
        return base
    grids = []
    for first in range(divisions + 1):
        if first / divisions < min_text_weight:
            continue
        for second in range(divisions - first + 1):
            weights = {'E1': first / divisions, 'E2': second / divisions,
                       'E3': (divisions - first - second) / divisions}
            rankings = {}
            for student in students:
                advisors = sorted({advisor for name in COMPONENTS for advisor in components[name].get(student, {})})
                scored = [(advisor, hybrid_score({name: components[name].get(student, {}).get(advisor)
                                                  for name in COMPONENTS}, weights)) for advisor in advisors]
                rankings[student] = [advisor for advisor, _ in sorted((item for item in scored if item[1] is not None),
                                                                     key=lambda item: (-item[1], item[0]))]
            metrics = ranking_metrics(rankings, validation_labels, k=k)
            grids.append({'weights': weights, 'rankings': rankings, 'metrics': metrics})
    common = set(students)
    for grid in grids:
        common &= {student for student, row in grid['metrics']['per_query'].items() if row['status'] == 'evaluated'}
    base['common_evaluation_students'] = sorted(common)
    for grid in grids:
        metrics = ranking_metrics({s: grid['rankings'][s] for s in sorted(common)}, validation_labels, k=k)
        base['grid_results'].append({'weights': grid['weights'], f'ndcg_at_{k}': metrics[f'ndcg_at_{k}'],
                                     f'mrr_at_{k}': metrics[f'mrr_at_{k}'],
                                     'evaluated_queries': metrics['evaluated_queries'],
                                     'judgment_coverage': metrics['judgment_coverage']})
    if not common:
        return base
    # Ties prefer balanced weights, then E1, then E2. No heldout selection.
    chosen = max(base['grid_results'], key=lambda r: (r[f'ndcg_at_{k}'], r[f'mrr_at_{k}'],
                 -sum((weight - 1/3)**2 for weight in r['weights'].values()), r['weights']['E1'], r['weights']['E2']))
    base.update(status='calibrated_validation_only', weights=chosen['weights'],
                **{f'ndcg_at_{k}': chosen[f'ndcg_at_{k}'], f'mrr_at_{k}': chosen[f'mrr_at_{k}']})
    base['calibration_label_sha256'] = hashlib.sha256(json.dumps(validation_labels, ensure_ascii=False,
                sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return base
