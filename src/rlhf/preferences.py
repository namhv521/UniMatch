from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)
    candidate_id: str = Field(min_length=1)
    assignments: dict[str, str] = Field(min_length=1)

class PreferenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    record_id: str = Field(min_length=1)
    timestamp: datetime
    context_ref: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    checkpoint_hash: str = Field(min_length=8)
    candidates: tuple[Candidate, Candidate]
    preference: Literal["A", "B", "abstain"]
    reviewer_role: str = Field(min_length=1)
    reviewer_ref: str = Field(min_length=1)
    consent_ref: str = Field(min_length=1)
    provenance_ref: str = Field(min_length=1)
    reason_code: str | None = None
    schema_version: Literal["1.0"] = "1.0"

    @model_validator(mode="after")
    def distinct_candidates(self):
        if self.candidates[0].candidate_id == self.candidates[1].candidate_id:
            raise ValueError("candidate IDs must be distinct")
        return self
