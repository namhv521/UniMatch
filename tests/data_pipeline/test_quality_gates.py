import pytest

from src.data_pipeline.curate.quality import QualityGateError, validate_quality


def _assignment(**overrides):
    value = {
        "assignment_id": "a-1",
        "entity_type": "student",
        "entity_id": "student-1",
        "tech_id": "python",
        "relation": "derived_from_thesis_supervision",
        "evidence_ref": "thesis-1#page-2",
        "source_ref": "fetch-1",
        "thesis_id": "thesis-1",
    }
    value.update(overrides)
    return value


def test_quality_gate_accepts_unique_evidenced_train_only_records():
    report = validate_quality(
        theses=[{"thesis_id": "thesis-1", "student_id": "student-1"}],
        advisors=[{"advisor_id": "advisor-1"}],
        assignments=[_assignment()],
        verified_supervision={"thesis-1": "advisor-1"},
        split_by_thesis={"thesis-1": "train"},
        fitted_thesis_ids={"thesis-1"},
    )

    assert report["ready"] is True
    assert report["errors"] == []


def test_quality_gate_rejects_an_empty_dataset():
    with pytest.raises(QualityGateError, match="no theses"):
        validate_quality(
            theses=[],
            advisors=[],
            assignments=[],
            verified_supervision={},
            split_by_thesis={},
            fitted_thesis_ids=set(),
        )


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_thesis",
        "missing_evidence",
        "invalid_propagation",
        "leakage",
    ],
)
def test_quality_gate_fails_closed(change):
    theses = [{"thesis_id": "thesis-1", "student_id": "student-1"}]
    assignments = [_assignment()]
    supervision = {"thesis-1": "advisor-1"}
    split = {"thesis-1": "train"}
    fitted = {"thesis-1"}
    if change == "duplicate_thesis":
        theses.append(dict(theses[0]))
    elif change == "missing_evidence":
        assignments[0]["evidence_ref"] = ""
    elif change == "invalid_propagation":
        assignments[0]["entity_id"] = "advisor-2"
        assignments[0]["entity_type"] = "advisor"
    else:
        split["thesis-1"] = "test"

    with pytest.raises(QualityGateError):
        validate_quality(
            theses=theses,
            advisors=[{"advisor_id": "advisor-1"}],
            assignments=assignments,
            verified_supervision=supervision,
            split_by_thesis=split,
            fitted_thesis_ids=fitted,
        )
