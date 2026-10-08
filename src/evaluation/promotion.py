"""Conservative validation gates; a pilot is never a full research release."""
import math

DEFAULT_SEEDS = [42, 123, 456, 789, 1024]


def promotion_decision(rows, *, expected_seeds=None, min_steps=2_000_000, min_ratio=.88):
    expected = set(DEFAULT_SEEDS if expected_seeds is None else expected_seeds)
    reasons = []
    if not rows or {row.get('seed') for row in rows} != expected or len(rows) != len(expected):
        reasons.append('missing_or_duplicate_seeds')
    for row in rows:
        metrics = row.get('metrics', {})
        target = row.get('target_timesteps', 0)
        if (row.get('training_status') != 'completed' or row.get('smoke') is not False
                or not isinstance(target, int) or target <= 0
                or row.get('training_timesteps', 0) < target):
            reasons.append('incomplete_training_manifest')
        if row.get('split') != 'validation' or row.get('training_scope') != 'curated-train' or not row.get('contract_verified'):
            reasons.append('unverified_real_validation_contract')
        if row.get('training_timesteps', 0) < min_steps:
            reasons.append('training_budget_incomplete')
        ratio = metrics.get('optimality_ratio')
        if not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio < min_ratio:
            reasons.append('compatibility_gate_failed')
        if any(metrics.get(key) != 0 for key in ('invalid_proposals', 'quota_violations', 'fallback_count')):
            reasons.append('invalid_or_repaired_policy')
        if metrics.get('coverage') != 1.0:
            reasons.append('incomplete_coverage')
    return {'promoted': not reasons, 'reasons': sorted(set(reasons)),
            'expected_seeds': sorted(expected), 'minimum_timesteps': min_steps,
            'minimum_optimality_ratio': min_ratio, 'fallback': 'Hungarian'}
