"""
Temporal split dataset module for KLTN.
Implements train/val/test split with anti-leakage temporal grouping.
"""


import numpy as np


def temporal_split_dataset(
    total_students: int = 198,
    val_ratio: float = 0.125,
    test_ratio: float = 0.125,
    random_seed: int = 42,
    *,
    records: list[dict] | None = None,
) -> dict[str, np.ndarray]:
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
    if not (0 <= val_ratio < 1 and 0 <= test_ratio < 1 and val_ratio + test_ratio < 1):
        raise ValueError('Invalid validation/test ratios')
    rng = np.random.RandomState(random_seed)
    if records is not None:
        if not records:
            raise ValueError('Dataset is empty')
        groups = {}
        for index, row in enumerate(records):
            student = str(row.get('student_id', '')).strip()
            try:
                year = int(row['submission_year'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('A verified submission_year is required') from exc
            if not student or year < 1900 or year > 2025:
                raise ValueError('Missing identity or year outside the temporal protocol')
            if student in groups and groups[student][0] != year:
                raise ValueError('Conflicting years for one student; adjudication required')
            groups.setdefault(student, (year, []))[1].append(index)
        recent = sorted(student for student, (year, _) in groups.items() if year == 2025)
        rng.shuffle(recent)
        n_train = int(len(recent) * (1 - val_ratio - test_ratio))
        n_val = int(len(recent) * val_ratio)
        membership = {student: 'train' for student in groups}
        membership.update({student: 'val' for student in recent[n_train:n_train + n_val]})
        membership.update({student: 'test' for student in recent[n_train + n_val:]})
        split = {name: np.array(sorted(i for student, (_, indices) in groups.items()
                                      if membership[student] == name for i in indices), dtype=np.int64)
                 for name in ('train', 'val', 'test')}
        validate_split(split, len(records))
        return split
    
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


def validate_split(split_indices: dict[str, np.ndarray], total: int) -> bool:
    """Validate that split is non-overlapping and complete."""
    if set(split_indices) != {'train', 'val', 'test'}:
        raise ValueError('Expected train, val and test')
    for indices in split_indices.values():
        if any(not isinstance(i, (int, np.integer)) for i in indices):
            raise ValueError('Indices must be integers')
        if len(indices) != len(set(indices)):
            raise ValueError('Repeated index within split')
    train = set(split_indices["train"])
    val = set(split_indices["val"])
    test = set(split_indices["test"])
    
    # Check no overlap
    if train & val or train & test or val & test:
        raise ValueError("Split sets overlap!")
    
    # Check complete coverage
    if train | val | test != set(range(total)):
        raise ValueError("Split doesn't cover all students!")
    
    return True


if __name__ == "__main__":
    import argparse
    import csv
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Split verified student/year records; demo is explicit')
    parser.add_argument('--input', type=Path, default=Path('data/curated/theses.csv'))
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    if not args.demo:
        if not args.input.is_file():
            parser.error(f'Missing curated data: {args.input}; use --demo only for synthetic checks')
        with args.input.open(encoding='utf-8-sig', newline='') as source:
            rows = list(csv.DictReader(source))
        split = temporal_split_dataset(records=rows)
        target = Path('data/curated/split_indices.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({key: values.tolist() for key, values in split.items()}, indent=2), encoding='utf-8')
        print({key: len(values) for key, values in split.items()})
        raise SystemExit(0)
    print('[DEMO ONLY] Synthetic years, not a curated dataset or research evidence')
    
    split = temporal_split_dataset(total_students=198, random_seed=42)
    
    print("[OK] Split completed:")
    print(f"   Train set: {len(split['train'])} students")
    print(f"   Val set:   {len(split['val'])} students")
    print(f"   Test set:  {len(split['test'])} students")
    print(f"   Total:     {sum(len(v) for v in split.values())} students")
    
    # Validate
    validate_split(split, 198)
    print("[OK] Validation passed - no leakage detected")
    
    print("\n[OK] Temporal split dataset module ready!")
