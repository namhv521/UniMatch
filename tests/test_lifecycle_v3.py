import numpy as np
import pytest


def test_streaming_retains_load_and_rejects_overflow_atomically():
    from src.rl.lifecycle_v3 import StreamingMatcher
    matcher = StreamingMatcher([1, 1])
    assert matcher.assign('s1', [.9, .1]) == 0
    with pytest.raises(ValueError):
        matcher.assign('s1', [.1, .9])
    assert matcher.assign('s2', [.8, .2]) == 1
    with pytest.raises(ValueError):
        matcher.assign('s3', [.5, .5])
    assert matcher.loads.tolist() == [1, 1]
    assert len(matcher.assignments) == 2


@pytest.mark.parametrize('quotas', [[], [-1, 1], [1.5], [float('nan')]])
def test_invalid_stream_capacity(quotas):
    from src.rl.lifecycle_v3 import StreamingMatcher
    with pytest.raises(ValueError):
        StreamingMatcher(quotas)


def test_invalid_arrival_does_not_consume_capacity():
    from src.rl.lifecycle_v3 import StreamingMatcher
    matcher = StreamingMatcher([1, 1])
    for scores in ([.5], [float('nan'), .1], [[.5, .6]], [2, .1]):
        with pytest.raises(ValueError):
            matcher.assign('s1', scores)
    assert matcher.loads.tolist() == [0, 0]


def test_simulation_is_reproducible_and_preserves_student_identity():
    from src.rl.lifecycle_v3 import simulate_streaming
    scores = np.random.default_rng(1).random((6, 3))
    events = simulate_streaming(scores, [2, 2, 2], seed=42)
    assert events == simulate_streaming(scores, [2, 2, 2], seed=42)
    assert sorted(event['student_index'] for event in events) == list(range(6))
    assert np.all(np.diff([event['arrival_time'] for event in events]) > 0)
    assert np.bincount([event['advisor_index'] for event in events], minlength=3).tolist() == [2, 2, 2]
    for event in events:
        assert event['compatibility'] == scores[event['student_index'], event['advisor_index']]
