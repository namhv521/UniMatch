"""
Temporal split dataset module for KLTN.
Implements train/val/test split with anti-leakage temporal grouping.
"""

import numpy as np
from typing import Tuple, Dict


def temporal_split_dataset(
    total_students: int = 198,
    val_ratio: float = 0.125,
    test_ratio: float = 0.125,
    random_seed: int = 42,
) -> Dict[str, np.ndarray]:
    """
    Perform temporal split on students dataset.
    
    Strategy:
    - Pre-2025: all → train
    - 2025: 75% train, 12.5% val, 12.5% test
    - Group by student_id (no mixing within student)
    
    Args:
        total_students: Total number of students (N)
        val_ratio: Validation split ratio (from 2025 cohort)
        test_ratio: Test split ratio (from 2025 cohort)
        random_seed: Random seed for reproducibility
        
    Returns:
        Dictionary with train/val/test indices
    """
    rng = np.random.RandomState(random_seed)
    
    # Simulate student years (50% pre-2025, 50% 2025)
    n_pre_2025 = total_students // 2
    n_2025 = total_students - n_pre_2025
    
    # Pre-2025 students → all train
    train_indices = list(range(n_pre_2025))
    
    # 2025 students → split 75/12.5/12.5
    indices_2025 = list(range(n_pre_2025, total_students))
    rng.shuffle(indices_2025)
    
    n_train_2025 = int(n_2025 * (1 - val_ratio - test_ratio))
    n_val_2025 = int(n_2025 * val_ratio)
    
    train_indices.extend(indices_2025[:n_train_2025])
    val_indices = indices_2025[n_train_2025:n_train_2025 + n_val_2025]
    test_indices = indices_2025[n_train_2025 + n_val_2025:]
    
    return {
        "train": np.array(sorted(train_indices), dtype=np.int32),
        "val": np.array(sorted(val_indices), dtype=np.int32),
        "test": np.array(sorted(test_indices), dtype=np.int32),
    }


def validate_split(split_indices: Dict[str, np.ndarray], total: int) -> bool:
    """Validate that split is non-overlapping and complete."""
    train = set(split_indices["train"])
    val = set(split_indices["val"])
    test = set(split_indices["test"])
    
    # Check no overlap
    if train & val or train & test or val & test:
        raise ValueError("Split sets overlap!")
    
    # Check complete coverage
    if len(train | val | test) != total:
        raise ValueError("Split doesn't cover all students!")
    
    return True


if __name__ == "__main__":
    # Execute when run as: python -m src.data_pipeline.split_dataset
    print("[*] Performing temporal split on dataset...")
    
    split = temporal_split_dataset(total_students=198, random_seed=42)
    
    print("[OK] Split completed:")
    print(f"   Train set: {len(split['train'])} students")
    print(f"   Val set:   {len(split['val'])} students")
    print(f"   Test set:  {len(split['test'])} students")
    print(f"   Total:     {sum(len(v) for v in split.values())} students")
    
    # Validate
    validate_split(split, 198)
    print(f"[OK] Validation passed - no leakage detected")
    
    print("\n[OK] Temporal split dataset module ready!")
