import numpy as np
import pytest

from src.models.data_contract import validate_matching_data


def test_capacity_contract():
    scores, quota = validate_matching_data([[.1, .8], [.9, .2]], [1, 1])
    assert scores.shape == (2, 2)
    np.testing.assert_array_equal(quota, [1, 1])
    for bad in [[], [[np.nan]], [[np.inf]], [[-.1]], [[1.1]]]:
        with pytest.raises(ValueError):
            validate_matching_data(bad, [1])


def test_huge_capacity_does_not_expand_unbounded_slots():
    _, quota = validate_matching_data([[.2]], [1e12])
    assert quota.tolist() == [1]
