import hashlib
import json

import numpy as np
import pytest


def checkpoint(tmp_path):
    path = tmp_path / 'model.zip'
    path.write_bytes(b'checkpoint integrity fixture')
    config = {'algorithm': 'ppo', 'seed': 42, 'dataset_sha256': 'abc',
              'learning_rate': .0003, 'fairness_weight': .15, 'gamma': .99}
    meta = {'configuration': config, 'requested_timesteps': 200000,
            'actual_timesteps': 200192, 'partial_data_smoke_only': False,
            'model_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix('.json').write_text(json.dumps(meta), encoding='utf-8')
    return path, config, meta


def test_checkpoint_hash_configuration_and_milestone_are_checked(tmp_path):
    from src.rl.evaluate_checkpoints import verify_checkpoint
    path, config, meta = checkpoint(tmp_path)
    assert verify_checkpoint(path, config, 200000, False) == meta
    with pytest.raises(ValueError, match='configuration'):
        verify_checkpoint(path, {**config, 'dataset_sha256': 'other'}, 200000, False)
    with pytest.raises(ValueError, match='milestone'):
        verify_checkpoint(path, config, 500000, False)
    with pytest.raises(ValueError, match='partial'):
        verify_checkpoint(path, config, 200000, True)
    path.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='integrity'):
        verify_checkpoint(path, config, 200000, False)


def test_ppo_rollout_passes_live_masks_and_finishes():
    from src.rl.evaluate_checkpoints import rollout_policy

    class Policy:
        def predict(self, observation, *, deterministic, action_masks):
            assert deterministic
            return np.flatnonzero(action_masks)[0], None

    result = rollout_policy(Policy(), 'ppo', [[.9, .1], [.8, .2]], [1, 1], seed=42)
    assert result['complete']
    assert result['assignments'] == [0, 1]
    assert result['invalid_proposals'] == result['quota_violations'] == 0
    assert result['mean_compatibility'] == pytest.approx(.55)


def test_unmasked_policy_truncates_without_fallback_or_complete_metrics():
    from src.rl.evaluate_checkpoints import rollout_policy

    class Policy:
        def predict(self, observation, *, deterministic):
            return 0, None

    result = rollout_policy(Policy(), 'dqn', [[.9, .1], [.8, .2]], [1, 1], seed=42)
    assert not result['complete'] and result['truncated']
    assert result['assignments'] == [0, -1]
    assert result['assigned_count'] == 1
    assert result['invalid_proposals'] == 19
    assert result['mean_compatibility'] is None
    assert result['optimality_ratio'] is None


def test_missing_checkpoints_produce_incomplete_forty_row_report(tmp_path):
    from src.rl.evaluate_checkpoints import benchmark_checkpoints
    report = benchmark_checkpoints([[.9, .1], [.8, .2]], [1, 1], dataset_sha256='abc',
                                   partial=False, model_dir=tmp_path)
    assert not report['complete']
    assert len(report['results']) == 40
    assert sum(row['status'] == 'missing_checkpoint' for row in report['results']) == 20
    assert sum(row['complete'] for row in report['results']) == 20
    assert {row['seed'] for row in report['results']} == {42, 123, 456, 789, 1024}
    assert len({row['strategy'] for row in report['results']}) == 8


def test_holdout_and_implicit_partial_evaluation_are_blocked(tmp_path):
    from src.rl.evaluate_checkpoints import benchmark_checkpoints
    for kwargs in ({'split': 'test', 'partial': False}, {'partial': True}):
        with pytest.raises(ValueError):
            benchmark_checkpoints([[.5]], [1], dataset_sha256='abc',
                                  model_dir=tmp_path, **kwargs)


def test_all_twenty_verified_policies_are_required_for_complete_report(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from src.rl import evaluate_checkpoints as module

    class Policy:
        observation_space = SimpleNamespace(shape=(3,))
        action_space = SimpleNamespace(n=1)

        def predict(self, observation, **kwargs):
            return 0, None

    monkeypatch.setattr(module, 'load_policy', lambda *args: Policy())
    _, config, metadata = checkpoint(tmp_path)
    for seed in module.SEEDS:
        for algorithm in module.RL_ALGORITHMS:
            path = tmp_path / f'{algorithm}_seed{seed}_steps200000.zip'
            path.write_bytes(b'checkpoint integrity fixture')
            metadata['configuration'] = {**config, 'seed': seed, 'algorithm': algorithm}
            path.with_suffix('.json').write_text(json.dumps(metadata), encoding='utf-8')
    report = module.benchmark_checkpoints([[.5]], [1], dataset_sha256='abc',
                                         partial=False, model_dir=tmp_path)
    assert report['complete'] and report['completed_rows'] == 40
    smoke = module.benchmark_checkpoints([[.5]], [1], dataset_sha256='abc',
                                        partial=False, model_dir=tmp_path, allow_partial=True)
    assert smoke['evaluation_complete'] and not smoke['complete'] and smoke['smoke_only']
    (tmp_path / 'ppo_seed42_steps200000.zip').write_bytes(b'tampered')
    report = module.benchmark_checkpoints([[.5]], [1], dataset_sha256='abc',
                                         partial=False, model_dir=tmp_path)
    assert not report['complete'] and report['completed_rows'] == 39
    errors = [r for r in report['results'] if r['status'] == 'checkpoint_error']
    assert len(errors) == 1 and 'integrity' in errors[0]['error']


def test_benchmark_preserves_large_quotas_for_policy_observation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from src.rl import evaluate_checkpoints as module
    path, _, metadata = checkpoint(tmp_path)
    target = tmp_path / 'ppo_seed42_steps200000.zip'
    target.write_bytes(path.read_bytes())
    target.with_suffix('.json').write_text(json.dumps(metadata), encoding='utf-8')

    class Policy:
        observation_space = SimpleNamespace(shape=(3,))
        action_space = SimpleNamespace(n=1)

        def predict(self, observation, **kwargs):
            assert observation[2] < .3  # Second student's actual load is 1/5, not 1/2.
            return 0, None

    monkeypatch.setattr(module, 'load_policy', lambda *args: Policy())
    report = module.benchmark_checkpoints([[.5], [.5]], [5], dataset_sha256='abc',
                                         partial=False, model_dir=tmp_path)
    ppo = next(row for row in report['results'] if row['strategy'] == 'ppo' and row['seed'] == 42)
    assert ppo['complete'], ppo
