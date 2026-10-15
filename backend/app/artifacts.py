"""Restore private serving files from PostgreSQL, without publishing them in Git."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath

ALLOWED_ROOTS = {"data/curated", "data/features", "outputs/checkpoints", "outputs/research-real", "outputs/research-filtered", "outputs/research-current", "outputs/benchmarks"}


def artifact_target(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if "\\" in relative or path.is_absolute() or ".." in path.parts or len(path.parts) != 3:
        raise ValueError("Invalid artifact path")
    if str(path.parent) not in ALLOWED_ROOTS or path.suffix not in {".json", ".npy", ".zip"}:
        raise ValueError("Artifact outside serving allowlist")
    target = root.joinpath(*path.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Artifact escapes product root")
    return target


def restore_artifacts(root: Path, database_url: str, bundle: str) -> int:
    import psycopg

    # Read and validate the complete immutable bundle before replacing local files.
    with psycopg.connect(database_url, connect_timeout=30) as connection:
        rows = connection.execute(
            "SELECT path, sha256, payload FROM serving_artifacts WHERE bundle = %s ORDER BY path", (bundle,)
        ).fetchall()
    if not rows or len(rows) > 250:
        raise RuntimeError("Serving artifact bundle missing or exceeds file limit")
    verified = []
    for relative, expected_hash, payload in rows:
        target = artifact_target(root, relative)
        content = bytes(payload)
        if len(content) > 64 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != expected_hash:
            raise RuntimeError("Serving artifact integrity check failed")
        verified.append((target, content))
    for target, content in verified:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".download")
        temporary.write_bytes(content)
        os.replace(temporary, target)
    return len(verified)
