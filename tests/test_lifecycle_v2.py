import numpy as np
import pytest


def test_explicit_preferences_change_assignment_without_overfilling():
    from src.rl.lifecycle_v2 import allocate_with_preferences, preference_matrix
    prefs = preference_matrix([[1, 0], [0]], 2)
    np.testing.assert_allclose(prefs, [[2 / 3, 1], [1, 0]])
    scores = [[.9, .8], [.8, .9]]
    assert allocate_with_preferences(scores, [1, 1], prefs, preference_weight=1).tolist() == [1, 0]
    assert allocate_with_preferences(scores, [1, 1]).tolist() == [0, 1]


def test_explicit_feedback_changes_objective():
    from src.rl.lifecycle_v2 import allocate_with_preferences
    assert allocate_with_preferences([[.9, .8]], [1, 1], feedback=[[0, 1]],
                                     feedback_weight=1).tolist() == [1]


@pytest.mark.parametrize('ranking', [[[0, 0]], [[-1]], [[2]], [[True]], [[0, 1, 0, 1]]])
def test_invalid_rankings_are_rejected(ranking):
    from src.rl.lifecycle_v2 import preference_matrix
    with pytest.raises(ValueError):
        preference_matrix(ranking, 2)


def test_missing_or_invalid_signals_are_rejected():
    from src.rl.lifecycle_v2 import allocate_with_preferences
    for kwargs in ({'preference_weight': 1}, {'preferences': [[float('nan')]]},
                   {'preferences': [[1, 0]]}, {'feedback_weight': -1},
                   {'feedback_weight': 1}):
        with pytest.raises(ValueError):
            allocate_with_preferences([[.5]], [1], **kwargs)


def test_bonus_only_for_successful_assignment_and_preserves_observation():
    from src.environment.extended_rewards import ExtendedRewardEnv
    env = ExtendedRewardEnv([[.9, .1], [.8, .2]], [1, 1],
                            preferences=[[1, 0], [1, 0]], role_matches=[[1, 0], [1, 0]],
                            preference_weight=.2, role_weight=.3, fairness_weight=0)
    obs, _ = env.reset()
    assert obs.shape == (6,)
    assert env.step(0)[1] == pytest.approx(1.4)
    _, reward, _, _, info = env.step(0)
    assert reward == -2
    assert info['preference_bonus'] == info['role_bonus'] == 0
    assert env.current_step == 1
    assert env.step(1)[1] == pytest.approx(.2)


def test_extended_reward_rejects_missing_signal():
    from src.environment.extended_rewards import ExtendedRewardEnv
    with pytest.raises(ValueError):
        ExtendedRewardEnv([[.5]], [1], role_weight=.2)
