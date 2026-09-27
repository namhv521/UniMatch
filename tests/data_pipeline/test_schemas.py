import csv
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.data_pipeline.schemas import (
    Advisor,
    EvidenceAssignment,
    ThesisDocument,
)


ROOT = Path(__file__).parents[2]


def _first_row(name: str) -> dict[str, str]:
    with (ROOT / "data/curated" / name).open(encoding="utf-8-sig", newline="") as stream:
        return next(csv.DictReader(stream))


def test_current_curated_records_validate_through_legacy_adapters():
    thesis = ThesisDocument.from_curated_row(_first_row("theses.csv"))
    advisor = Advisor.from_curated_row(_first_row("advisors.csv"))

    assert thesis.student_id and thesis.content_sha256
    assert advisor.advisor_id and advisor.profile_status.value in {"found", "manual_required"}


@pytest.mark.parametrize(
    ("field", "value"),
    [("entity_id", "bad id / slash"), ("evidence_ref", ""), ("source_ref", "")],
)
def test_evidence_assignment_rejects_invalid_ids_and_missing_evidence(field, value):
    valid = {
        "assignment_id": "assignment-1",
        "entity_type": "student",
        "entity_id": "11236160",
        "tech_id": "python",
        "relation": "mentioned_in_thesis",
        "confidence": 0.9,
        "evidence_ref": "thesis-1#page-3",
        "source_ref": "fetch-1",
        "created_by": "rule",
        "taxonomy_version": "2026-09-27",
        "review_status": "accepted",
    }
    valid[field] = value

    with pytest.raises(ValidationError):
        EvidenceAssignment.model_validate(valid)


def test_evidence_assignment_rejects_unknown_enums():
    with pytest.raises(ValidationError):
        EvidenceAssignment.model_validate(
            {
                "assignment_id": "assignment-1",
                "entity_type": "person",
                "entity_id": "11236160",
                "tech_id": "python",
                "relation": "guessed",
                "confidence": 0.9,
                "evidence_ref": "thesis-1#page-3",
                "source_ref": "fetch-1",
                "created_by": "robot",
                "taxonomy_version": "2026-09-27",
                "review_status": "accepted",
            }
        )
