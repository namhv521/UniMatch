from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from src.data_pipeline.schemas import ID_PATTERN, StrictModel


class Technology(StrictModel):
    tech_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(min_length=1)
    parent: str = Field(min_length=1)
    type: Literal["language", "framework", "database", "method", "domain", "tool"]
    status: str = Field(min_length=1)

    @field_validator("aliases")
    @classmethod
    def reject_blank_aliases(cls, aliases: list[str]) -> list[str]:
        if any(not alias.strip() for alias in aliases):
            raise ValueError("taxonomy aliases must not be blank")
        return aliases


class TechTaxonomy(StrictModel):
    version: str = Field(min_length=1)
    technologies: list[Technology]

    @model_validator(mode="after")
    def reject_ambiguous_aliases(self) -> "TechTaxonomy":
        tech_ids: set[str] = set()
        aliases: dict[str, str] = {}
        for technology in self.technologies:
            if technology.tech_id in tech_ids:
                raise ValueError(f"duplicate tech_id: {technology.tech_id}")
            tech_ids.add(technology.tech_id)
            for alias in technology.aliases:
                key = alias.casefold().strip()
                owner = aliases.setdefault(key, technology.tech_id)
                if owner != technology.tech_id:
                    raise ValueError(f"ambiguous taxonomy alias: {alias}")
        return self


class TechMention(StrictModel):
    tech_id: str = Field(pattern=ID_PATTERN)
    matched_alias: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_span(self) -> "TechMention":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        expected = f"{self.source_ref}#char-{self.start}:{self.end}"
        if self.evidence_ref != expected:
            raise ValueError("evidence_ref must identify the matched span")
        return self


def _alias_pattern(alias: str) -> re.Pattern[str]:
    pieces = [re.escape(piece) for piece in alias.casefold().split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(pieces) + r"(?!\w)")


def extract_tech_mentions(
    text: str, taxonomy: TechTaxonomy, *, source_ref: str
) -> list[TechMention]:
    """Match active taxonomy aliases deterministically with word boundaries."""
    folded = text.casefold()
    candidates: list[tuple[int, int, str, str]] = []
    for technology in taxonomy.technologies:
        if technology.status != "active":
            continue
        for alias in technology.aliases:
            for match in _alias_pattern(alias).finditer(folded):
                candidates.append((match.start(), match.end(), technology.tech_id, match.group()))

    chosen: list[TechMention] = []
    seen: set[str] = set()
    for start, end, tech_id, alias in sorted(
        candidates, key=lambda item: (item[0], -(item[1] - item[0]), item[2])
    ):
        if tech_id in seen:
            continue
        seen.add(tech_id)
        chosen.append(
            TechMention(
                tech_id=tech_id,
                matched_alias=alias,
                start=start,
                end=end,
                evidence_ref=f"{source_ref}#char-{start}:{end}",
                source_ref=source_ref,
                taxonomy_version=taxonomy.version,
            )
        )
    return chosen
