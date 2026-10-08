import pytest

from src.domain import (
    Advisor,
    Assignment,
    Quota,
    Student,
    Thesis,
    validate_assignments,
)


def valid_domain():
    students = [Student("student-1", "An"), Student("student-2", "Binh")]
    advisors = [Advisor("advisor-1", "Dr A"), Advisor("advisor-2", "Dr B")]
    theses = [
        Thesis("thesis-1", "student-1", "Topic A"),
        Thesis("thesis-2", "student-2", "Topic B"),
    ]
    quotas = [Quota("advisor-1", 1), Quota("advisor-2", 1)]
    assignments = [
        Assignment("student-1", "advisor-1", "thesis-1"),
        Assignment("student-2", "advisor-2", "thesis-2"),
    ]
    return students, advisors, theses, quotas, assignments


@pytest.mark.parametrize(
    "model,args",
    [
        (Student, ("bad id", "An")),
        (Advisor, ("", "Dr A")),
        (Thesis, ("thesis-1", "unknown id", "Topic")),
        (Quota, ("advisor-1", -1)),
        (Assignment, ("student-1", "advisor-1", "bad id")),
    ],
)
def test_domain_models_reject_invalid_ids_and_capacity(model, args):
    with pytest.raises(ValueError):
        model(*args)


def test_domain_models_keep_stable_ids_unchanged():
    student = Student("student-1", "An")

    assert student.student_id == "student-1"


def test_validate_assignments_accepts_complete_feasible_matching():
    validate_assignments(*valid_domain())


@pytest.mark.parametrize(
    "replacement",
    [
        Assignment("student-404", "advisor-1", "thesis-1"),
        Assignment("student-1", "advisor-404", "thesis-1"),
        Assignment("student-1", "advisor-1", "thesis-404"),
    ],
)
def test_validate_assignments_rejects_unknown_references(replacement):
    students, advisors, theses, quotas, assignments = valid_domain()
    assignments[0] = replacement

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas, assignments)


def test_validate_assignments_rejects_thesis_owned_by_another_student():
    students, advisors, theses, quotas, assignments = valid_domain()
    assignments[0] = Assignment("student-2", "advisor-1", "thesis-1")

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas, assignments)


@pytest.mark.parametrize(
    "duplicate",
    [
        Assignment("student-1", "advisor-2", "thesis-2"),
        Assignment("student-2", "advisor-2", "thesis-1"),
    ],
)
def test_validate_assignments_rejects_duplicate_student_or_thesis(duplicate):
    students, advisors, theses, quotas, assignments = valid_domain()
    assignments[1] = duplicate

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas, assignments)


def test_validate_assignments_rejects_advisor_over_capacity():
    students, advisors, theses, quotas, assignments = valid_domain()
    assignments[1] = Assignment("student-2", "advisor-1", "thesis-2")

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas, assignments)


def test_validate_assignments_rejects_missing_quota():
    students, advisors, theses, quotas, assignments = valid_domain()

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas[:1], assignments)


def test_validate_assignments_requires_complete_student_and_thesis_coverage():
    students, advisors, theses, quotas, assignments = valid_domain()

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas, assignments[:1])


def test_validate_assignments_rejects_duplicate_domain_ids():
    students, advisors, theses, quotas, assignments = valid_domain()
    students.append(Student("student-1", "Duplicate"))

    with pytest.raises(ValueError):
        validate_assignments(students, advisors, theses, quotas, assignments)
