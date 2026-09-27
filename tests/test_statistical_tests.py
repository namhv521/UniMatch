import pytest


def test_five_pair_exact_limit_and_zero_difference_status():
    from src.rl.statistical_tests import paired_statistics
    result = paired_statistics([1, 2, 4, 7, 11], [0, 0, 0, 0, 0])
    assert result['wilcoxon_p'] == pytest.approx(.0625)
    assert result['df'] == 4
    equal = paired_statistics([1] * 5, [1] * 5)
    assert equal['status'] == 'identical_observations'
    assert equal['t_p'] is None
    with pytest.raises(ValueError):
        paired_statistics([1, 2], [1, 2])


def test_holm_preserves_original_order_and_bounds():
    from src.rl.statistical_tests import holm_adjust
    assert holm_adjust([.03, .01, .2]) == pytest.approx([.06, .03, .2])
