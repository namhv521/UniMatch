import numpy as np
import pytest

from src.environment import MatchingEnv


def test_reward_matches_spec_and_rejects_full_advisor():
    env = MatchingEnv(n_students=2, n_advisors=2, max_quota=1)
    env.reset(seed=42)
    expected = float(env.compatibility[0, 0]) - 0.15 * 0.25
    _, reward, done, _, info = env.step(0)
    assert reward == pytest.approx(expected)
    assert not done
    assert env.action_masks().tolist() == [False, True]
    _, reward, done, _, info = env.step(0)
    assert reward == -2.0
    assert not done
    assert env.current_step == 1
    assert info['invalid_proposals'] == 1
    assert env.load.tolist() == [1, 0]
    _, _, done, _, info = env.step(1)
    assert done
    assert info['quota_violations'] == 0
    with pytest.raises(RuntimeError):
        env.step(1)


def test_default_capacity_is_feasible():
    env = MatchingEnv()
    assert env.n_advisors * env.max_quota >= env.n_students


def test_infeasible_capacity_and_bad_actions_rejected():
    with pytest.raises(ValueError):
        MatchingEnv(n_students=3, n_advisors=2, max_quota=1)
    env = MatchingEnv(n_students=2, n_advisors=2, max_quota=1)
    env.reset(seed=42)
    for action in [-1, 2, 0.5]:
        with pytest.raises(ValueError):
            env.step(action)


def test_seed_and_gym_contract():
    from gymnasium.utils.env_checker import check_env
    env = MatchingEnv(n_students=2, n_advisors=2, max_quota=1)
    first, _ = env.reset(seed=42)
    second, _ = env.reset(seed=42)
    np.testing.assert_array_equal(first, second)
    check_env(env, skip_render_check=True)
