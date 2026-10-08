import pytest
from pydantic import ValidationError

from src.data_pipeline.extract.advisor import AdvisorSupervision
from src.data_pipeline.extract.tech import TechMention, TechTaxonomy, extract_tech_mentions
from src.data_pipeline.extract.thesis import extract_thesis
from src.data_pipeline.identity.resolve import normalize_person_name, stable_advisor_id
from src.data_pipeline.provenance.assignments import propagate_thesis_technology


SOURCE_HASH = "a" * 64


def _artifact(*, include_advisor_evidence: bool = True) -> dict:
    evidence = [
        {
            "field": "student_id",
            "value": "11223344",
            "page": 1,
            "quote": "Mã sinh viên: 11223344",
            "kind": "direct",
        },
        {
            "field": "student_name",
            "value": "Nguyễn Văn An",
            "page": 1,
            "quote": "Sinh viên: Nguyễn Văn An",
            "kind": "direct",
        },
        {
            "field": "thesis_title",
            "value": "Học máy với Python",
            "page": 1,
            "quote": "Học máy với Python",
            "kind": "direct",
        },
        {
            "field": "submission_year",
            "value": "2025",
            "page": 1,
            "quote": "Hà Nội, 2025",
            "kind": "direct",
        },
    ]
    if include_advisor_evidence:
        evidence.append(
            {
                "field": "advisor_name",
                "value": "TS. Nguyễn Ngọc Tuấn",
                "page": 2,
                "quote": "Giảng viên hướng dẫn: TS. Nguyễn Ngọc Tuấn",
                "kind": "direct",
            }
        )
    return {
        "source_sha256": SOURCE_HASH,
        "source_file": "11223344.pdf",
        "profile": {
            "student_id": "11223344",
            "student_name": "Nguyễn Văn An",
            "submission_year": 2025,
            "advisor_name": "TS. Nguyễn Ngọc Tuấn",
            "thesis_title": "Học máy với Python",
            "abstract": "Xây dựng Machine Learning bằng Python.",
            "evidence": evidence,
        },
    }


def _taxonomy() -> TechTaxonomy:
    return TechTaxonomy.model_validate(
        {
            "version": "2026-09-28",
            "technologies": [
                {
                    "tech_id": "python",
                    "name": "Python",
                    "aliases": ["python"],
                    "parent": "programming_language",
                    "type": "language",
                    "status": "active",
                },
                {
                    "tech_id": "react",
                    "name": "React",
                    "aliases": ["react", "react.js"],
                    "parent": "frontend",
                    "type": "framework",
                    "status": "active",
                },
                {
                    "tech_id": "machine_learning",
                    "name": "Machine Learning",
                    "aliases": ["machine learning", "học máy"],
                    "parent": "artificial_intelligence",
                    "type": "domain",
                    "status": "active",
                },
            ],
        }
    )


def test_identity_normalization_removes_titles_and_keeps_a_stable_advisor_id():
    assert normalize_person_name("  TS. NGUYỄN   NGỌC TUẤN ") == "nguyễn ngọc tuấn"
    assert stable_advisor_id("TS. Nguyễn Ngọc Tuấn") == stable_advisor_id(
        "Nguyễn Ngọc Tuấn"
    )
    assert stable_advisor_id("Nguyễn Ngọc Tuấn") != stable_advisor_id(
        "Nguyễn Ngọc Tuân"
    )


def test_thesis_extraction_builds_only_an_evidence_backed_supervision_relation():
    extraction = extract_thesis(_artifact(), crawl_run_id="run-04")

    assert extraction.thesis.student_id == "11223344"
    assert extraction.thesis.thesis_id == f"thesis-{SOURCE_HASH[:20]}"
    assert extraction.supervision is not None
    assert extraction.supervision.verified is True
    assert extraction.supervision.evidence_ref.endswith("#page-2")


def test_thesis_extraction_fails_closed_when_advisor_evidence_is_missing():
    extraction = extract_thesis(
        _artifact(include_advisor_evidence=False), crawl_run_id="run-04"
    )

    assert extraction.supervision is None


def test_thesis_identity_requires_direct_student_id_evidence():
    artifact = _artifact()
    artifact["profile"]["evidence"] = [
        item for item in artifact["profile"]["evidence"] if item["field"] != "student_id"
    ]

    with pytest.raises(ValueError, match="student_id evidence"):
        extract_thesis(artifact, crawl_run_id="run-04")


def test_alias_extraction_is_deterministic_and_does_not_match_inside_words():
    text = "Reactive UI, React.js, PYTHON và học máy. React"

    matches = extract_tech_mentions(text, _taxonomy(), source_ref="thesis-1#abstract")

    assert [(match.tech_id, match.matched_alias) for match in matches] == [
        ("react", "react.js"),
        ("python", "python"),
        ("machine_learning", "học máy"),
    ]
    assert all(text[match.start : match.end].casefold() == match.matched_alias for match in matches)


def test_propagation_creates_three_deterministic_assignments_only_for_verified_supervision():
    extraction = extract_thesis(_artifact(), crawl_run_id="run-04")
    mention = extract_tech_mentions(
        extraction.thesis.title,
        _taxonomy(),
        source_ref=f"{extraction.thesis.thesis_id}#title",
    )[0]

    first = propagate_thesis_technology(extraction.thesis, extraction.supervision, mention)
    second = propagate_thesis_technology(extraction.thesis, extraction.supervision, mention)

    assert [assignment.model_dump() for assignment in first] == [
        assignment.model_dump() for assignment in second
    ]
    assert {assignment.entity_type.value for assignment in first} == {
        "thesis",
        "student",
        "advisor",
    }
    assert next(item for item in first if item.entity_type.value == "thesis").relation.value == (
        "mentioned_in_thesis"
    )
    assert {
        item.relation.value for item in first if item.entity_type.value in {"student", "advisor"}
    } == {"derived_from_thesis_supervision"}
    assert all(item.relation.value != "self_declared" for item in first)


def test_propagation_fails_closed_for_unverified_or_invalid_evidence():
    extraction = extract_thesis(_artifact(), crawl_run_id="run-04")
    mention = extract_tech_mentions(
        extraction.thesis.title,
        _taxonomy(),
        source_ref=f"{extraction.thesis.thesis_id}#title",
    )[0]
    unverified = extraction.supervision.model_copy(update={"verified": False})

    assert propagate_thesis_technology(extraction.thesis, unverified, mention) == []
    wrong_source = extraction.supervision.model_copy(update={"source_ref": "sha256:" + "b" * 64})
    assert propagate_thesis_technology(extraction.thesis, wrong_source, mention) == []
    unrelated_mention = mention.model_copy(update={"source_ref": "thesis-other#title"})
    assert propagate_thesis_technology(extraction.thesis, extraction.supervision, unrelated_mention) == []
    with pytest.raises(ValidationError):
        AdvisorSupervision.model_validate(
            {
                "thesis_id": extraction.thesis.thesis_id,
                "advisor_id": stable_advisor_id("Nguyễn Ngọc Tuấn"),
                "advisor_name_normalized": "nguyễn ngọc tuấn",
                "relation": "advisor_of_thesis",
                "verified": True,
                "evidence_ref": "",
                "source_ref": f"sha256:{SOURCE_HASH}",
            }
        )


def test_tech_mention_rejects_a_span_that_does_not_match_its_evidence_reference():
    with pytest.raises(ValidationError, match="evidence_ref"):
        TechMention.model_validate(
            {
                "tech_id": "python",
                "matched_alias": "python",
                "start": 4,
                "end": 10,
                "evidence_ref": "thesis-1#char-0:6",
                "source_ref": "thesis-1",
                "taxonomy_version": "2026-09-28",
            }
        )
