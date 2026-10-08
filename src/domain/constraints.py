"""Hard constraints for complete student-advisor matchings."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TypeVar

from .models import Advisor, Assignment, Quota, Student, Thesis


T = TypeVar("T")


def _by_id(items: Iterable[T], attribute: str) -> dict[str, T]:
    values = list(items)
    indexed = {getattr(item, attribute): item for item in values}
    if len(indexed) != len(values):
        raise ValueError(f"duplicate {attribute}")
    return indexed


def validate_assignments(
    students: Iterable[Student],
    advisors: Iterable[Advisor],
    theses: Iterable[Thesis],
    quotas: Iterable[Quota],
    assignments: Iterable[Assignment],
) -> None:
    """Raise ``ValueError`` unless assignments form one complete feasible matching."""

    students_by_id = _by_id(students, "student_id")
    advisors_by_id = _by_id(advisors, "advisor_id")
    theses_by_id = _by_id(theses, "thesis_id")
    quotas_by_advisor = _by_id(quotas, "advisor_id")
    assignment_list = list(assignments)

    if quotas_by_advisor.keys() != advisors_by_id.keys():
        raise ValueError("each advisor must have exactly one quota")

    assigned_students: set[str] = set()
    assigned_theses: set[str] = set()
    advisor_load: Counter[str] = Counter()

    for assignment in assignment_list:
        if assignment.student_id not in students_by_id:
            raise ValueError(f"unknown student_id: {assignment.student_id}")
        if assignment.advisor_id not in advisors_by_id:
            raise ValueError(f"unknown advisor_id: {assignment.advisor_id}")
        thesis = theses_by_id.get(assignment.thesis_id)
        if thesis is None:
            raise ValueError(f"unknown thesis_id: {assignment.thesis_id}")
        if thesis.student_id != assignment.student_id:
            raise ValueError("thesis does not belong to assigned student")
        if assignment.student_id in assigned_students:
            raise ValueError(f"duplicate student assignment: {assignment.student_id}")
        if assignment.thesis_id in assigned_theses:
            raise ValueError(f"duplicate thesis assignment: {assignment.thesis_id}")

        assigned_students.add(assignment.student_id)
        assigned_theses.add(assignment.thesis_id)
        advisor_load[assignment.advisor_id] += 1

    if assigned_students != students_by_id.keys() or assigned_theses != theses_by_id.keys():
        raise ValueError("assignments must cover every student and thesis exactly once")

    for advisor_id, load in advisor_load.items():
        if load > quotas_by_advisor[advisor_id].capacity:
            raise ValueError(f"advisor capacity exceeded: {advisor_id}")
