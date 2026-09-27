import numpy as np
import pytest

from src.data_pipeline.split_dataset import temporal_split_dataset, validate_split


def test_real_years_and_student_groups():
    rows = [{'student_id': str(i), 'submission_year': 2025} for i in range(16)]
    rows += [{'student_id': 'old', 'submission_year': 2024}] * 2
    split = temporal_split_dataset(records=rows, random_seed=42)
    assert {16, 17} <= set(split['train'])
    assert len(split['val']) == len(split['test']) == 2
    validate_split(split, len(rows))
    for indices in split.values():
        assert (16 in indices) == (17 in indices)


def test_missing_year_and_cross_year_identity_fail_closed():
    for rows in [
        [{'student_id': 'a'}],
        [{'student_id': 'a', 'submission_year': 2026}],
        [{'student_id': 'a', 'submission_year': 2024},
         {'student_id': 'a', 'submission_year': 2025}],
    ]:
        with pytest.raises(ValueError):
            temporal_split_dataset(records=rows)


def test_indices_are_exact_and_no_duplicates():
    for split in [
        {'train': np.array([-1, 0]), 'val': np.array([1]), 'test': np.array([])},
        {'train': np.array([0, 0]), 'val': np.array([1]), 'test': np.array([2])},
    ]:
        with pytest.raises(ValueError):
            validate_split(split, 3)
