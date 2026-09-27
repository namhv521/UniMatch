"""User-requested feature schema with grounded evidence."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: str
    value: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=3)
    kind: Literal['direct', 'inferred']


class ThesisExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    student_id: str | None
    student_name: str | None
    submission_year: int | None = Field(ge=1900, le=2100)
    major: str | None
    advisor_name: str | None
    thesis_title: str | None
    abstract: str | None
    field_category: str | None
    web_languages: list[str]
    app_languages: list[str]
    frontend_frameworks: list[str]
    backend_frameworks: list[str]
    ai_frameworks: list[str]
    database_cache: list[str]
    app_db_backend: list[str]
    ai_problems: list[str]
    data_tools: list[str]
    data_models: list[str]
    research_methods: list[str]
    primary_role: str | None
    secondary_roles: list[str]
    evidence: list[Evidence]
    warnings: list[str]
