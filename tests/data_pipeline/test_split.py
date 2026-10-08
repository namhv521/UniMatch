import pytest

from src.data_pipeline.split import split_temporally, validate_disjoint


def test_temporal_split_groups_students_and_keeps_future_separate():
    records = [
        {"student_id": "old", "submission_year": 2024},
        *({"student_id": f"s{i}", "submission_year": 2025} for i in range(8)),
        {"student_id": "future", "submission_year": 2026},
        {"student_id": "s0", "submission_year": 2025},
    ]

    split = split_temporally(records, seed=42)

    assert "old" in split["train"]
    assert len(set(split["train"]) & set(split["validation"])) == 0
    assert len(set(split["train"]) & set(split["test"])) == 0
    assert split["future"] == ["future"]
    assert sum("s0" in values for values in split.values()) == 1


def test_overlap_aborts_pipeline():
    with pytest.raises(ValueError, match="overlap"):
        validate_disjoint({"train": ["s1"], "validation": ["s1"], "test": [], "future": []})
