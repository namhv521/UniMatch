"""Cryptographic verification helpers for frozen semester RL suites and source audits."""
from __future__ import annotations

import json
from pathlib import Path

from src.features.fresh_suite import digest


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify_suites(suites, *, expected_manifest_sha256=None):
    suites = Path(suites).resolve()
    if expected_manifest_sha256 is not None and digest(suites / 'manifest.json') != expected_manifest_sha256:
        raise ValueError('frozen_suite_manifest_hash_mismatch')
    manifest = _read(suites / 'manifest.json')
    for relative, sha in manifest['artifacts'].items():
        path = (suites / relative).resolve()
        if not path.is_relative_to(suites) or digest(path) != sha:
            raise ValueError('frozen_suite_hash_mismatch')
    return manifest


def verify_source_audit(path, expected_suite_sha256):
    audit = _read(path)
    if audit.get('suite_manifest_sha256') != expected_suite_sha256 or audit.get('score_parity_verified') is not True:
        raise ValueError('source_audit_suite_or_parity_mismatch')
    for source, sha in {**audit['source_files'], **audit['raw_files']}.items():
        if digest(source) != sha:
            raise ValueError('source_audit_hash_mismatch')
    return audit
