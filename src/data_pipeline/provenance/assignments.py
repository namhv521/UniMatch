from __future__ import annotations

import hashlib

from src.data_pipeline.extract.advisor import AdvisorSupervision
from src.data_pipeline.extract.tech import TechMention
from src.data_pipeline.schemas import (
    CreatedBy,
    EntityType,
    EvidenceAssignment,
    EvidenceRelation,
    ReviewStatus,
    ThesisDocument,
)


def _assignment_id(entity_type: EntityType, entity_id: str, mention: TechMention) -> str:
    value = "\0".join(
        (
            entity_type.value,
            entity_id,
            mention.tech_id,
            mention.evidence_ref,
            mention.taxonomy_version,
        )
    )
    return f"assignment-{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def propagate_thesis_technology(
    thesis: ThesisDocument,
    supervision: AdvisorSupervision | None,
    mention: TechMention,
) -> list[EvidenceAssignment]:
    """Propagate one grounded thesis mention only across a verified supervision edge."""
    if (
        supervision is None
        or not supervision.verified
        or supervision.thesis_id != thesis.thesis_id
        or supervision.source_ref != thesis.source_ref
        or not mention.source_ref.startswith(f"{thesis.thesis_id}#")
        or mention.evidence_ref
        != f"{mention.source_ref}#char-{mention.start}:{mention.end}"
        or not mention.evidence_ref.strip()
        or not mention.source_ref.strip()
    ):
        return []

    entities = (
        (EntityType.THESIS, thesis.thesis_id, EvidenceRelation.MENTIONED_IN_THESIS),
        (EntityType.STUDENT, thesis.student_id, EvidenceRelation.DERIVED_FROM_SUPERVISION),
        (
            EntityType.ADVISOR,
            supervision.advisor_id,
            EvidenceRelation.DERIVED_FROM_SUPERVISION,
        ),
    )
    return [
        EvidenceAssignment(
            assignment_id=_assignment_id(entity_type, entity_id, mention),
            entity_type=entity_type,
            entity_id=entity_id,
            tech_id=mention.tech_id,
            relation=relation,
            confidence=mention.confidence,
            evidence_ref=mention.evidence_ref,
            source_ref=thesis.source_ref,
            created_by=CreatedBy.RULE,
            taxonomy_version=mention.taxonomy_version,
            review_status=ReviewStatus.ACCEPTED,
        )
        for entity_type, entity_id, relation in entities
    ]
