import json

import numpy as np
import pytest

from src.environment.matching_env import MatchingEnv
from src.rl.training import ROOT, TrainingConfig, build_environment, run_manifest


def test_full_training_uses_only_real_train_split():
    env = build_environment(TrainingConfig('DQN')).unwrapped
    indices = json.loads((ROOT / 'data/curated/split_indices.json').read_text())['indices']['train']
    matrix = np.load(ROOT / 'data/features/compatibility_matrix_v2.npy', allow_pickle=False)
    assert env.n_advisors == 38
    assert env.n_students == len(indices)
    np.testing.assert_allclose(env.compatibility, matrix[indices])


def test_smoke_provenance_cannot_claim_real_dataset():
    full = run_manifest(TrainingConfig('DQN'))
    smoke = run_manifest(TrainingConfig('DQN').with_smoke())
    assert smoke['training_scope'] == 'synthetic-smoke'
    assert smoke['dataset_hash'] != full['dataset_hash']
    assert full['observation_shape'] == [114]
    assert full['action_count'] == 38


@pytest.mark.parametrize('scores', [np.array([[np.nan, .2]]), np.empty((0, 2))])
def test_env_rejects_nonfinite_or_empty_scores(scores):
    with pytest.raises(ValueError):
        MatchingEnv(scores, np.array([1, 1]))


def test_env_rejects_step_after_done():
    env = MatchingEnv(np.array([[.9, .2]]), np.array([1, 1]))
    env.reset()
    env.step(0)
    with pytest.raises(ValueError, match='terminated'):
        env.step(1)
