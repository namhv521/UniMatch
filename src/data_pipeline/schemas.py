from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _legacy_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    URL_UNREACHABLE = "url_unreachable"
    BLOCKED = "blocked"
    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    MANUAL_REQUIRED = "manual_required"
    NOT_ATTEMPTED = "not_attempted"


class ExtractionStatus(StrEnum):
    ACCEPTED = "accepted"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class EntityType(StrEnum):
    STUDENT = "student"
    ADVISOR = "advisor"
    THESIS = "thesis"


class EvidenceRelation(StrEnum):
    MENTIONED_IN_THESIS = "mentioned_in_thesis"
    ADVISOR_OF_THESIS = "advisor_of_thesis"
    SELF_DECLARED = "self_declared"
    INFERRED = "inferred"
    DERIVED_FROM_SUPERVISION = "derived_from_thesis_supervision"


class CreatedBy(StrEnum):
    RULE = "rule"
    LLM = "llm"
    HUMAN = "human"


class ReviewStatus(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class ThesisDocument(StrictModel):
    thesis_id: str = Field(pattern=ID_PATTERN)
    student_id: str = Field(pattern=ID_PATTERN)
    student_name_normalized: str = Field(min_length=1)
    title: str = Field(min_length=1)
    abstract: str | None = None
    keywords_raw: list[str]
    document_uri: str = Field(min_length=1)
    submission_year: int = Field(ge=2000, le=2100)
    source_ref: str = Field(min_length=1)
    crawl_run_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    extraction_status: ExtractionStatus

    @classmethod
    def from_curated_row(cls, row: dict[str, Any]) -> Self:
        review = _legacy_bool(row.get("needs_review"))
        return cls(
            thesis_id=row["thesis_id"],
            student_id=row["student_id"],
            student_name_normalized=row["student_name"],
            title=row["thesis_title"],
            abstract=row.get("abstract") or None,
            keywords_raw=[],
            document_uri=row["source_file"],
            submission_year=int(row["submission_year"]),
            source_ref=row["source_sha256"],
            crawl_run_id="legacy-baseline",
            content_sha256=row["source_sha256"],
            extraction_status=(
                ExtractionStatus.REVIEW_REQUIRED if review else ExtractionStatus.ACCEPTED
            ),
        )


class Advisor(StrictModel):
    advisor_id: str = Field(pattern=ID_PATTERN)
    name_raw: str = Field(min_length=1)
    name_normalized: str = Field(min_length=1)
    academic_title: str | None = None
    department: str = Field(min_length=1)
    profile_url: str | None = None
    profile_status: ProfileStatus
    source_ref: str = Field(min_length=1)
    crawl_run_id: str = Field(min_length=1)
    identity_confidence: float = Field(ge=0, le=1)
    manual_override: bool = False

    @classmethod
    def from_curated_row(cls, row: dict[str, Any]) -> Self:
        review = _legacy_bool(row.get("needs_review"))
        url = row.get("source_url") or None
        return cls(
            advisor_id=row["advisor_id"],
            name_raw=row["advisor_name"],
            name_normalized=row["advisor_name"],
            academic_title=row.get("academic_title") or None,
            department="FIT-NEU",
            profile_url=url,
            profile_status=ProfileStatus.MANUAL_REQUIRED if review else ProfileStatus.FOUND,
            source_ref=url or f"legacy:{row['advisor_id']}",
            crawl_run_id="legacy-baseline",
            identity_confidence=0.5 if review else 1.0,
        )


class EvidenceAssignment(StrictModel):
    assignment_id: str = Field(pattern=ID_PATTERN)
    entity_type: EntityType
    entity_id: str = Field(pattern=ID_PATTERN)
    tech_id: str = Field(pattern=ID_PATTERN)
    relation: EvidenceRelation
    confidence: float = Field(ge=0, le=1)
    evidence_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    created_by: CreatedBy
    taxonomy_version: str = Field(min_length=1)
    review_status: ReviewStatus

    @field_validator("evidence_ref", "source_ref")
    @classmethod
    def reject_blank_reference(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reference must not be blank")
        return value
