from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip()


class SimulateRequest(StrictModel):
    mode: Literal["semantic", "non_rl", "rl", "rl_research"]
    algorithm: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    dataset: Literal["sample-2x2", "sample-3x2", "real-train", "real-validation", "real-test"]
    seed: int = Field(default=42, ge=0, le=2_147_483_647)


class RecommendRequest(StrictModel):
    title: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class FeedbackRequest(StrictModel):
    mode: Literal["semantic", "non_rl", "rl", "rl_research"]
    algorithm: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    helpful: bool
