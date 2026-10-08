import numpy as np

from src.evaluation.benchmark import evaluate_baselines, evaluate_policy
from src.evaluation.promotion import promotion_decision


class AlwaysFirst:
    def predict(self, observation, **kwargs):
        return 0, None


def test_invalid_policy_has_bounded_repair_and_cannot_promote():
    scores = np.array([[.9, .1], [.8, .7]])
    result = evaluate_policy(AlwaysFirst(), scores, np.array([1, 1]), 'DQN')
    assert result['assignments'] == [0, 1]
    assert result['metrics']['invalid_proposals'] == 1
    assert result['metrics']['quota_violations'] == 0
    assert result['metrics']['fallback_count'] == 1
    assert not promotion_decision([result], expected_seeds=[42])['promoted']


def test_baselines_use_identical_capacity_and_scores():
    rows = evaluate_baselines(np.array([[.9, .1], [.8, .7]]), np.array([1, 1]), [42])
    hungarian = next(row for row in rows if row['algorithm'] == 'Hungarian')
    assert hungarian['metrics']['mean_compatibility'] == .8
    assert all(row['metrics']['quota_violations'] == 0 for row in rows)


def test_promotion_requires_real_validation_complete_seeds_and_verified_contract():
    row = {'seed':42, 'split':'validation', 'training_scope':'curated-train',
           'training_status':'completed', 'smoke':False, 'target_timesteps':2_000_000,
           'contract_verified':True, 'metrics': {'mean_compatibility':.8,
           'optimality_ratio':1.0, 'invalid_proposals':0, 'quota_violations':0,
           'fallback_count':0, 'coverage':1.0}, 'training_timesteps':2_000_000}
    assert not promotion_decision([row], expected_seeds=[42,123])['promoted']
    assert promotion_decision([row], expected_seeds=[42])['promoted']
    assert not promotion_decision([{**row, 'training_scope':'synthetic-smoke'}], expected_seeds=[42])['promoted']
    assert not promotion_decision([{**row, 'training_status':'running'}], expected_seeds=[42])['promoted']
    assert not promotion_decision([{**row, 'smoke':True}], expected_seeds=[42])['promoted']
    assert not promotion_decision([{**row, 'target_timesteps':3_000_000}], expected_seeds=[42])['promoted']
