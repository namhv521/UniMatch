"""Deterministic source mentions with exact original-text evidence offsets."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml


TAXONOMY_GROUPS = {
    'research_domain_tags', 'topic_tags', 'programming_languages',
    'frameworks_libraries', 'databases', 'ml_ai_methods', 'data_engineering_tools',
    'cloud_devops_tools', 'security_network_tools', 'software_engineering_methods',
    'research_methods', 'math_statistics_topics',
}


def load_taxonomy(path: Path | str | None = None) -> dict:
    path = Path(path) if path is not None else Path(__file__).resolve().parents[2] / 'configs/data/taxonomy_v1.yaml'
    taxonomy = yaml.safe_load(path.read_text(encoding='utf-8'))
    if (not isinstance(taxonomy, dict) or taxonomy.get('schema_version') != '1.0'
            or taxonomy.get('taxonomy_version') != '1.0' or not isinstance(taxonomy.get('groups'), dict)):
        raise ValueError('invalid_taxonomy_contract')
    stopwords = {unicodedata.normalize('NFC', item).casefold() for item in taxonomy.get('stopwords', [])}
    for group, entries in taxonomy['groups'].items():
        if group not in TAXONOMY_GROUPS:
            raise ValueError('unknown_taxonomy_group')
        if not isinstance(entries, dict):
            raise ValueError('invalid_taxonomy_entries')
        used = {}
        for tag, definition in entries.items():
            if not re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', tag) or not isinstance(definition, dict):
                raise ValueError('invalid_taxonomy_id')
            for key in ('aliases', 'case_sensitive_aliases'):
                aliases = definition.get(key, [])
                if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
                    raise ValueError('invalid_taxonomy_aliases')
                for alias in aliases:
                    normalized = unicodedata.normalize('NFC', alias).casefold()
                    if key == 'aliases' and normalized in stopwords:
                        raise ValueError('ambiguous_short_alias')
                    if normalized in used and used[normalized] != tag:
                        raise ValueError('ambiguous_alias')
                    used[normalized] = tag
    return taxonomy


def taxonomy_ids(taxonomy: dict) -> set[str]:
    return {tag for entries in taxonomy['groups'].values() for tag in entries}


def _nfc_view(text: str) -> tuple[str, list[int], list[int]]:
    """Map NFC matching characters back to complete original combining clusters."""
    normalized, starts, ends = [], [], []
    start = 0
    while start < len(text):
        end = start + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        cluster = unicodedata.normalize('NFC', text[start:end])
        normalized.append(cluster)
        starts.extend([start] * len(cluster))
        ends.extend([end] * len(cluster))
        start = end
    return ''.join(normalized), starts, ends


def normalize_mentions(text: str, taxonomy: dict) -> list[dict]:
    if not isinstance(text, str):
        raise TypeError('text_must_be_string')
    view, starts, ends = _nfc_view(text)
    matches = []
    for group, entries in taxonomy['groups'].items():
        for tag, definition in entries.items():
            for key in ('aliases', 'case_sensitive_aliases'):
                flags = re.IGNORECASE if key == 'aliases' else 0
                for alias in definition.get(key, []):
                    normalized_alias = unicodedata.normalize('NFC', alias)
                    pattern = r'(?<!\w)' + re.escape(normalized_alias) + r'(?!\w)'
                    for match in re.finditer(pattern, view, flags):
                        left, right = starts[match.start()], ends[match.end() - 1]
                        matches.append({'tag': tag, 'group': group, 'matched_text': text[left:right],
                                        'start': left, 'end': right, 'evidence_type': 'inferred_from_thesis'})
    # Prefer the most specific phrase inside each group. Different groups may
    # legitimately describe the same concept (e.g. topic NLP and NLP method).
    accepted = []
    for match in sorted(matches, key=lambda m: (-(m['end'] - m['start']), m['start'], m['group'], m['tag'])):
        if any(previous['group'] == match['group'] and match['start'] < previous['end']
               and previous['start'] < match['end'] for previous in accepted):
            continue
        accepted.append(match)
    return sorted(accepted, key=lambda m: (m['start'], m['end'], m['group'], m['tag']))
