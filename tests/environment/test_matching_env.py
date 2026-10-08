import numpy as np
import pytest

from src.environment.matching_env import MatchingEnv


def test_reset_observation_and_action_mask_follow_spec():
    env = MatchingEnv(
        compatibility=np.array([[0.9, 0.2], [0.4, 0.8]], dtype=np.float32),
        capacities=np.array([1, 1]),
    )

    observation, info = env.reset(seed=7)

    np.testing.assert_allclose(observation, [0.9, 0.2, 1.0, 1.0, 0.0, 0.0])
    np.testing.assert_array_equal(env.action_masks(), [True, True])
    assert info == {"student_index": 0}


def test_step_updates_load_mask_and_next_student_deterministically():
    env = MatchingEnv(
        compatibility=np.array([[0.9, 0.2], [0.4, 0.8]], dtype=np.float32),
        capacities=np.array([1, 1]),
    )
    env.reset()

    observation, reward, terminated, truncated, info = env.step(0)

    np.testing.assert_allclose(observation, [0.4, 0.8, 0.0, 1.0, 1.0, 0.0])
    np.testing.assert_array_equal(env.action_masks(), [False, True])
    assert reward == pytest.approx(0.8625)
    assert not terminated
    assert not truncated
    assert info == {"student_index": 1, "invalid_action": False}


def test_invalid_full_advisor_action_is_penalized_without_advancing():
    env = MatchingEnv(
        compatibility=np.array([[0.9, 0.2], [0.4, 0.8]], dtype=np.float32),
        capacities=np.array([1, 1]),
    )
    env.reset()
    env.step(0)

    observation, reward, terminated, truncated, info = env.step(0)

    np.testing.assert_allclose(observation, [0.4, 0.8, 0.0, 1.0, 1.0, 0.0])
    assert reward == pytest.approx(-2.0)
    assert not terminated
    assert not truncated
    assert info == {"student_index": 1, "invalid_action": True}


def test_episode_terminates_after_every_student_is_assigned():
    env = MatchingEnv(np.array([[0.9, 0.2]], dtype=np.float32), np.array([1, 0]))
    env.reset()

    observation, _, terminated, truncated, info = env.step(0)

    np.testing.assert_allclose(observation, np.zeros(6, dtype=np.float32))
    assert terminated
    assert not truncated
    assert info == {"student_index": 1, "invalid_action": False}


@pytest.mark.parametrize(
    ("compatibility", "capacities", "message"),
    [
        ([[0.5, 0.4]], [1], "advisor count"),
        ([[0.5]], [-1], "non-negative"),
        ([[0.5], [0.4]], [1], "insufficient capacity"),
        ([[1.1]], [1], "between 0 and 1"),
    ],
)
def test_environment_rejects_invalid_problem_instances(compatibility, capacities, message):
    with pytest.raises(ValueError, match=message):
        MatchingEnv(np.asarray(compatibility), np.asarray(capacities))
