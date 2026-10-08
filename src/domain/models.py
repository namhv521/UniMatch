"""Typed records for the matching domain."""

from __future__ import annotations

import re
from dataclasses import dataclass


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")


def _require_id(value: str, field: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{field} must be a stable ID")


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must not be blank")


@dataclass(frozen=True, slots=True)
class Student:
    student_id: str
    name: str

    def __post_init__(self) -> None:
        _require_id(self.student_id, "student_id")
        _require_text(self.name, "name")


@dataclass(frozen=True, slots=True)
class Advisor:
    advisor_id: str
    name: str

    def __post_init__(self) -> None:
        _require_id(self.advisor_id, "advisor_id")
        _require_text(self.name, "name")


@dataclass(frozen=True, slots=True)
class Thesis:
    thesis_id: str
    student_id: str
    title: str

    def __post_init__(self) -> None:
        _require_id(self.thesis_id, "thesis_id")
        _require_id(self.student_id, "student_id")
        _require_text(self.title, "title")


@dataclass(frozen=True, slots=True)
class Quota:
    advisor_id: str
    capacity: int

    def __post_init__(self) -> None:
        _require_id(self.advisor_id, "advisor_id")
        if isinstance(self.capacity, bool) or not isinstance(self.capacity, int) or self.capacity < 0:
            raise ValueError("capacity must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class Assignment:
    student_id: str
    advisor_id: str
    thesis_id: str

    def __post_init__(self) -> None:
        _require_id(self.student_id, "student_id")
        _require_id(self.advisor_id, "advisor_id")
        _require_id(self.thesis_id, "thesis_id")
