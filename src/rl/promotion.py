"""Fail-closed validation gate; Exact remains default when evidence is incomplete."""
import math

SEEDS = {42, 123, 456, 789, 1024}


def promotion_decision(candidate, greedy, minimum_ratio=.88):
    reasons = []
    for name, rows in [('candidate', candidate), ('greedy', greedy)]:
        if len(rows) != 5 or {row.get('seed') for row in rows} != SEEDS:
            reasons.append(f'{name}: five distinct required seeds missing')
        for row in rows:
            if row.get('split') != 'val' or not row.get('complete') or row.get('partial_data') is not False:
                reasons.append(f'{name}: incomplete/non-validation evidence')
            for metric in ['mean_compatibility', 'quota_violations', 'invalid_proposals', 'optimality_ratio']:
                value = row.get(metric)
                if not isinstance(value, (float, int)) or not math.isfinite(value):
                    reasons.append(f'{name}: invalid {metric}')
    hashes = {row.get('dataset_sha256') for row in candidate + greedy}
    if len(hashes) != 1 or not next(iter(hashes), None):
        reasons.append('Dataset snapshots do not match')
    if not reasons:
        reference = {row['seed']: row for row in greedy}
        for row in candidate:
            if row['quota_violations'] != 0 or row['invalid_proposals'] != 0:
                reasons.append('Constraint gate failed')
            if row['mean_compatibility'] < reference[row['seed']]['mean_compatibility']:
                reasons.append('Candidate is below Greedy on a paired seed')
            if row['optimality_ratio'] < minimum_ratio or row['optimality_ratio'] > 1 + 1e-8:
                reasons.append('Optimality ratio gate failed')
    return {'promote': not reasons, 'engine': 'candidate' if not reasons else 'exact',
            'reasons': sorted(set(reasons)), 'minimum_ratio': minimum_ratio}
