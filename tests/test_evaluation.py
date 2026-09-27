import pytest


def test_metrics_do_not_index_unassigned_as_last_advisor():
    from src.rl.benchmark import evaluate_assignment
    with pytest.raises(ValueError):
        evaluate_assignment([[.1, .9]], [1, 1], [-1])
    metrics = evaluate_assignment([[0, 0]], [1, 1], [0])
    assert metrics['optimality_ratio'] is None
    assert metrics['historical_top1_accuracy'] is None


def test_metrics_have_known_exact_ratio_and_quota_check():
    from src.rl.benchmark import evaluate_assignment
    metrics = evaluate_assignment([[.9, .8], [.95, .1]], [1, 1], [1, 0], historical=[1, 0])
    assert metrics['optimality_ratio'] == pytest.approx(1)
    assert metrics['historical_top1_accuracy'] == 1
    assert metrics['quota_violations'] == 0


def test_promotion_fails_closed():
    from src.rl.promotion import promotion_decision
    assert not promotion_decision([], [])['promote']
    good = [{'seed': s, 'mean_compatibility': .9, 'quota_violations': 0,
             'invalid_proposals': 0, 'optimality_ratio': .95, 'split': 'val',
             'complete': True, 'dataset_sha256': 'same', 'partial_data': False}
            for s in [42, 123, 456, 789, 1024]]
    baseline = [{**row, 'mean_compatibility': .8} for row in good]
    assert promotion_decision(good, baseline)['promote']
    good[0]['mean_compatibility'] = float('nan')
    assert not promotion_decision(good, baseline)['promote']
