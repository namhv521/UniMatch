from __future__ import annotations

from typing import Any

from src.data_pipeline.extract.advisor import AdvisorSupervision, supervision_from_evidence
from src.data_pipeline.identity.resolve import normalize_person_name
from src.data_pipeline.schemas import StrictModel, ThesisDocument


class ThesisExtraction(StrictModel):
    thesis: ThesisDocument
    supervision: AdvisorSupervision | None = None


def _direct_evidence(profile: dict[str, Any], field: str, expected: object) -> bool:
    return any(
        item.get("field") == field
        and item.get("kind") == "direct"
        and str(item.get("value", "")).strip() == str(expected).strip()
        and str(item.get("quote", "")).strip()
        for item in profile.get("evidence", [])
    )


def extract_thesis(artifact: dict[str, Any], *, crawl_run_id: str) -> ThesisExtraction:
    """Validate a grounded LLM artifact and materialize its canonical thesis."""
    profile = artifact.get("profile") or {}
    student_id = str(profile.get("student_id") or "").strip()
    if not _direct_evidence(profile, "student_id", student_id):
        raise ValueError("direct student_id evidence is required")

    source_hash = str(artifact.get("source_sha256") or "").strip().lower()
    thesis_id = f"thesis-{source_hash[:20]}"
    source_ref = f"sha256:{source_hash}"
    thesis = ThesisDocument(
        thesis_id=thesis_id,
        student_id=student_id,
        student_name_normalized=normalize_person_name(
            str(profile.get("student_name") or "")
        ),
        title=str(profile.get("thesis_title") or ""),
        abstract=profile.get("abstract") or None,
        keywords_raw=list(profile.get("keywords_raw") or []),
        document_uri=str(artifact.get("source_file") or ""),
        submission_year=profile.get("submission_year"),
        source_ref=source_ref,
        crawl_run_id=crawl_run_id,
        content_sha256=source_hash,
        extraction_status="accepted",
    )
    supervision = supervision_from_evidence(
        thesis_id=thesis_id,
        advisor_name=profile.get("advisor_name"),
        evidence=list(profile.get("evidence") or []),
        source_ref=source_ref,
    )
    return ThesisExtraction(thesis=thesis, supervision=supervision)
