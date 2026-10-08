import pytest

from src.environment.reward import matching_reward


def test_reward_penalizes_concentrating_load_by_exact_spec_weight():
    reward = matching_reward(0.8, [0, 0], [1, 0])

    assert reward == pytest.approx(0.7625)


def test_reward_rewards_reducing_load_variance_by_exact_spec_weight():
    reward = matching_reward(0.5, [1, 0], [1, 1])

    assert reward == pytest.approx(0.5375)


def test_reward_applies_exact_invalid_proposal_penalty():
    reward = matching_reward(0.0, [1, 0], [1, 0], invalid=True)

    assert reward == pytest.approx(-2.0)


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        ((1.1, [0, 0], [1, 0]), {}, "compatibility"),
        ((0.5, [0, 0], [1]), {}, "same shape"),
        ((0.5, [0, -1], [1, 0]), {}, "non-negative"),
        ((0.5, [0, 0], [1, 0]), {"compatibility_weight": -1}, "weights"),
    ],
)
def test_reward_rejects_invalid_inputs(args, kwargs, message):
    with pytest.raises(ValueError, match=message):
        matching_reward(*args, **kwargs)
