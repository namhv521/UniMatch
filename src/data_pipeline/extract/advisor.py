from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from src.data_pipeline.identity.resolve import normalize_person_name, stable_advisor_id
from src.data_pipeline.schemas import ID_PATTERN, Advisor, ProfileStatus, StrictModel


class AdvisorSupervision(StrictModel):
    thesis_id: str = Field(pattern=ID_PATTERN)
    advisor_id: str = Field(pattern=ID_PATTERN)
    advisor_name_normalized: str = Field(min_length=1)
    relation: Literal["advisor_of_thesis"] = "advisor_of_thesis"
    verified: bool
    evidence_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)


def supervision_from_evidence(
    *,
    thesis_id: str,
    advisor_name: str | None,
    evidence: list[dict[str, Any]],
    source_ref: str,
) -> AdvisorSupervision | None:
    """Build a supervision edge only from matching direct evidence."""
    if not advisor_name:
        return None
    normalized_name = normalize_person_name(advisor_name)
    match = next(
        (
            item
            for item in evidence
            if item.get("field") == "advisor_name"
            and item.get("kind") == "direct"
            and normalize_person_name(str(item.get("value", ""))) == normalized_name
            and str(item.get("quote", "")).strip()
            and isinstance(item.get("page"), int)
            and item["page"] >= 1
        ),
        None,
    )
    if match is None:
        return None
    return AdvisorSupervision(
        thesis_id=thesis_id,
        advisor_id=stable_advisor_id(advisor_name),
        advisor_name_normalized=normalized_name,
        verified=True,
        evidence_ref=f"{thesis_id}#page-{match['page']}",
        source_ref=source_ref,
    )


def extract_advisor(
    name_raw: str,
    *,
    department: str,
    source_ref: str,
    crawl_run_id: str,
    profile_url: str | None = None,
    profile_status: ProfileStatus = ProfileStatus.FOUND,
    identity_confidence: float = 1.0,
) -> Advisor:
    """Create a canonical advisor record from a grounded profile identity."""
    return Advisor(
        advisor_id=stable_advisor_id(name_raw),
        name_raw=name_raw,
        name_normalized=normalize_person_name(name_raw),
        academic_title=None,
        department=department,
        profile_url=profile_url,
        profile_status=profile_status,
        source_ref=source_ref,
        crawl_run_id=crawl_run_id,
        identity_confidence=identity_confidence,
    )
