from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from typing import Any


SPLIT_NAMES = ("train", "validation", "test", "future")


def validate_disjoint(split: Mapping[str, Iterable[str]]) -> None:
    seen: set[str] = set()
    for name in SPLIT_NAMES:
        values = set(split.get(name, []))
        overlap = seen & values
        if overlap:
            raise ValueError(f"student overlap across splits: {sorted(overlap)}")
        seen.update(values)


def split_temporally(records: Iterable[Mapping[str, Any]], seed: int = 42) -> dict[str, list[str]]:
    year_by_student: dict[str, int] = {}
    for record in records:
        student_id = str(record["student_id"])
        year = int(record["submission_year"])
        previous = year_by_student.setdefault(student_id, year)
        if previous != year:
            raise ValueError(f"student {student_id} spans multiple submission years")

    historical = sorted(student_id for student_id, year in year_by_student.items() if year < 2025)
    current = sorted(student_id for student_id, year in year_by_student.items() if year == 2025)
    future = sorted(student_id for student_id, year in year_by_student.items() if year > 2025)
    random.Random(seed).shuffle(current)
    train_count = int(len(current) * 0.75)
    remaining = len(current) - train_count
    validation_count = remaining // 2
    split = {
        "train": sorted([*historical, *current[:train_count]]),
        "validation": sorted(current[train_count : train_count + validation_count]),
        "test": sorted(current[train_count + validation_count :]),
        "future": future,
    }
    validate_disjoint(split)
    return split
