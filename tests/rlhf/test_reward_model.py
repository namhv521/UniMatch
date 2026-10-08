import pytest
from datetime import datetime, timezone
from src.rlhf.preferences import Candidate, PreferenceRecord
from src.rlhf.reward_model import validate_training_readiness

def record(record_id="r1"):
    candidates = (Candidate(candidate_id="a", assignments={"s":"x"}), Candidate(candidate_id="b", assignments={"s":"y"}))
    return PreferenceRecord(record_id=record_id, timestamp=datetime.now(timezone.utc), context_ref="ctx", model_version="m1", checkpoint_hash="12345678", candidates=candidates, preference="A", reviewer_role="domain-expert", reviewer_ref=record_id, consent_ref="consent", provenance_ref="audit")

def test_readiness_fails_closed_without_genuine_volume():
    with pytest.raises(ValueError, match="insufficient"): validate_training_readiness([], 2, .5)

def test_readiness_detects_duplicates_and_passes_valid_records():
    with pytest.raises(ValueError, match="duplicate"): validate_training_readiness([record(), record()], 2, .5)
    result = validate_training_readiness([record("r1"), record("r2")], 2, .5)
    assert result["ready"]

def test_singleton_contexts_and_disagreement_fail_closed():
    first, second = record("r1"), record("r2")
    second = second.model_copy(update={"context_ref": "other"})
    with pytest.raises(ValueError, match="comparable"): validate_training_readiness([first, second], 2, .5)
    second = record("r2").model_copy(update={"preference": "B"})
    with pytest.raises(ValueError, match="below"): validate_training_readiness([first, second], 2, .75)
