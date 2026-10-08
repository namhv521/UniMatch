from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class QualityGateError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _duplicates(records: Iterable[Mapping[str, Any]], key: str) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        value = str(record.get(key, ""))
        if not value or value in seen:
            duplicates.add(value or "<missing>")
        seen.add(value)
    return duplicates


def validate_quality(
    *,
    theses: list[Mapping[str, Any]],
    advisors: list[Mapping[str, Any]],
    assignments: list[Mapping[str, Any]],
    verified_supervision: Mapping[str, str],
    split_by_thesis: Mapping[str, str],
    fitted_thesis_ids: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    if not theses:
        errors.append("no theses in curated dataset")
    if not advisors:
        errors.append("no advisors in curated dataset")
    for records, key in ((theses, "thesis_id"), (advisors, "advisor_id"), (assignments, "assignment_id")):
        duplicates = _duplicates(records, key)
        if duplicates:
            errors.append(f"duplicate or missing {key}: {sorted(duplicates)}")

    thesis_by_id = {str(row["thesis_id"]): row for row in theses}
    for assignment in assignments:
        assignment_id = str(assignment.get("assignment_id", "<missing>"))
        if not assignment.get("evidence_ref") or not assignment.get("source_ref"):
            errors.append(f"assignment {assignment_id} missing evidence")
        if assignment.get("relation") != "derived_from_thesis_supervision":
            continue
        thesis_id = str(assignment.get("thesis_id", ""))
        thesis = thesis_by_id.get(thesis_id)
        entity_type = assignment.get("entity_type")
        entity_id = assignment.get("entity_id")
        valid = thesis is not None and (
            (entity_type == "student" and entity_id == thesis.get("student_id"))
            or (entity_type == "advisor" and entity_id == verified_supervision.get(thesis_id))
        )
        if not valid:
            errors.append(f"assignment {assignment_id} has unverified propagation")

    leaked = sorted(thesis_id for thesis_id in fitted_thesis_ids if split_by_thesis.get(thesis_id) != "train")
    if leaked:
        errors.append(f"fit leakage outside train: {leaked}")
    if errors:
        raise QualityGateError(errors)
    return {
        "ready": True,
        "errors": [],
        "counts": {
            "theses": len(theses),
            "advisors": len(advisors),
            "assignments": len(assignments),
        },
    }
