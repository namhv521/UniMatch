from __future__ import annotations
from collections import Counter, defaultdict
from .preferences import PreferenceRecord

def validate_training_readiness(records: list[PreferenceRecord], minimum_records: int = 100,
                                minimum_agreement: float = 0.7) -> dict:
    if len(records) < minimum_records:
        raise ValueError(f"insufficient genuine preferences: {len(records)}/{minimum_records}")
    ids = [record.record_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate preference record IDs")
    groups = defaultdict(list)
    for record in records:
        if record.preference != "abstain":
            pair = tuple(sorted(candidate.candidate_id for candidate in record.candidates))
            groups[(record.context_ref, pair)].append(record)
    comparable = []
    for group in groups.values():
        reviewers = {record.reviewer_ref for record in group}
        if len(reviewers) >= 2:
            counts = Counter(record.preference for record in group)
            comparable.append(max(counts.values()) / len(group))
    if not comparable:
        raise ValueError("insufficient comparable multi-review evidence")
    agreement = sum(comparable) / len(comparable)
    if agreement < minimum_agreement:
        raise ValueError(f"reviewer agreement below threshold: {agreement:.3f}")
    return {"ready": True, "records": len(records), "agreement": agreement}
