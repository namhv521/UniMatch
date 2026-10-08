from __future__ import annotations

import hashlib
import re
import unicodedata


_ACADEMIC_TITLES = re.compile(
    r"^(?:(?:gs|pgs|ts|ths|th\.?\s*s|dr|phd)\.?\s+)+",
    flags=re.IGNORECASE,
)
_SPACES = re.compile(r"\s+")
_NON_ID = re.compile(r"[^a-z0-9]+")


def normalize_person_name(name: str) -> str:
    """Return the canonical comparison form for a person's name."""
    normalized = unicodedata.normalize("NFC", name).strip()
    normalized = _ACADEMIC_TITLES.sub("", normalized)
    return _SPACES.sub(" ", normalized).casefold()


def stable_advisor_id(name: str) -> str:
    """Derive the same readable ID for academic-title and case variants."""
    normalized = normalize_person_name(name).replace("đ", "d")
    ascii_name = "".join(
        character
        for character in unicodedata.normalize("NFKD", normalized)
        if not unicodedata.combining(character)
    )
    slug = _NON_ID.sub("-", ascii_name).strip("-")
    if not slug:
        raise ValueError("advisor name does not contain an identity")
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:8]
    return f"advisor-{slug}-{digest}"
