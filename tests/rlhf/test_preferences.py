from datetime import datetime, timezone
import pytest
from src.rlhf.collector import append_preference, load_preferences
from src.rlhf.preferences import Candidate, PreferenceRecord

def record(record_id="r1"):
    candidates = (Candidate(candidate_id="a", assignments={"s":"x"}), Candidate(candidate_id="b", assignments={"s":"y"}))
    return PreferenceRecord(record_id=record_id, timestamp=datetime.now(timezone.utc), context_ref="ctx", model_version="m1", checkpoint_hash="12345678", candidates=candidates, preference="A", reviewer_role="domain-expert", reviewer_ref=record_id, consent_ref="consent", provenance_ref="audit")

def test_append_only_and_duplicate_rejection(tmp_path):
    path = tmp_path / "preferences.jsonl"; append_preference(path, record())
    assert load_preferences(path)[0].record_id == "r1"
    with pytest.raises(ValueError, match="duplicate"): append_preference(path, record())

def test_consent_and_distinct_candidates_required():
    data = record().model_dump(); data["consent_ref"] = ""
    with pytest.raises(ValueError): PreferenceRecord.model_validate(data)
