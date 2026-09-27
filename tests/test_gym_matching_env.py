import numpy as np
import pytest


def test_real_matrix_and_unequal_quota_are_used():
    from src.environment.gym_matching_env import GymMatchingEnv
    scores = np.array([[.9, .1], [.8, .2], [.3, .7]], dtype=np.float32)
    env = GymMatchingEnv(scores, [1, 2])
    obs, _ = env.reset(seed=42)
    np.testing.assert_allclose(obs[:2], scores[0])
    env.step(0)
    assert env.action_masks().tolist() == [False, True]
    env.step(1)
    _, _, done, truncated, info = env.step(1)
    assert done and not truncated
    assert info['assignments'] == [0, 1, 1]
    assert info['mean_compatibility'] == pytest.approx(.6)


def test_invalid_policy_is_bounded_without_dropping_student():
    from src.environment.gym_matching_env import GymMatchingEnv
    env = GymMatchingEnv([[.9, .1], [.8, .2]], [1, 1], max_proposals=3)
    env.reset(seed=42)
    env.step(0)
    env.step(0)
    _, _, done, truncated, info = env.step(0)
    assert not done and truncated
    assert info['assigned_count'] == 1
    assert info['invalid_proposals'] == 2
    assert info['assignments'] == [0, -1]


def test_real_env_passes_gym_checker():
    from gymnasium.utils.env_checker import check_env

    from src.environment.gym_matching_env import GymMatchingEnv
    check_env(GymMatchingEnv([[.9, .1], [.8, .2]], [1, 1]), skip_render_check=True)
