from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .training import CONTRACT_FIELDS


def save_checkpoint(model, path, *, algorithm: str, seed: int, run_manifest: dict | None = None) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save(path)
    archive = path.with_suffix(".zip")
    manifest = {
        "algorithm": algorithm,
        "seed": seed,
        "checkpoint": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    if run_manifest:
        manifest.update(run_manifest)
        manifest.update({"checkpoint": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
    path.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def validate_resume_manifest(manifest: dict, config) -> None:
    expected = config.contract()
    mismatches = [field for field in CONTRACT_FIELDS if manifest.get(field) != expected[field]]
    if manifest.get("smoke") or manifest.get("status") != "completed":
        mismatches.append("completion_state")
    if mismatches:
        raise ValueError(f"incompatible resume: {', '.join(mismatches)}")


def verified_checkpoint(manifest_path: Path, manifest: dict) -> Path:
    checkpoint = Path(manifest_path).parent / manifest.get("checkpoint", "")
    if not checkpoint.is_file():
        raise ValueError("resume checkpoint is missing")
    actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if actual != manifest.get("sha256"):
        raise ValueError("resume checkpoint hash mismatch")
    return checkpoint
