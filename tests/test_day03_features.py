"""Tests for DAY-03 features specification and split dataset."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_pipeline.split_dataset import temporal_split_dataset, validate_split


def test_features_spec_exists():
    """Test that features specification document exists."""
    repo_root = Path(__file__).parent.parent
    spec_file = repo_root / "docs" / "features_specification.md"
    assert spec_file.exists(), "features_specification.md not found"
    assert spec_file.stat().st_size > 0, "features_specification.md is empty"
    print("[OK] Features specification exists")


def test_temporal_split():
    """Test temporal split creates correct proportions."""
    split = temporal_split_dataset(total_students=198, random_seed=42)
    
    assert len(split["train"]) == 173, f"Expected 173 train, got {len(split['train'])}"
    assert len(split["val"]) == 12, f"Expected 12 val, got {len(split['val'])}"
    assert len(split["test"]) == 13, f"Expected 13 test, got {len(split['test'])}"
    
    total = sum(len(v) for v in split.values())
    assert total == 198, f"Expected 198 total, got {total}"
    print("[OK] Temporal split proportions correct")


def test_no_data_leakage():
    """Test that train/val/test sets don't overlap."""
    split = temporal_split_dataset(total_students=198, random_seed=42)
    
    train_set = set(split["train"])
    val_set = set(split["val"])
    test_set = set(split["test"])
    
    assert len(train_set & val_set) == 0, "Train/Val overlap detected!"
    assert len(train_set & test_set) == 0, "Train/Test overlap detected!"
    assert len(val_set & test_set) == 0, "Val/Test overlap detected!"
    print("[OK] No data leakage - sets are disjoint")


def test_validate_split_function():
    """Test split validation logic."""
    split = temporal_split_dataset(total_students=198, random_seed=42)
    assert validate_split(split, 198), "Split validation failed"
    print("[OK] Split validation passed")


if __name__ == "__main__":
    test_features_spec_exists()
    test_temporal_split()
    test_no_data_leakage()
    test_validate_split_function()
    print("\n[OK] All DAY-03 tests passed!")
