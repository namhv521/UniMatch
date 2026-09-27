from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


BASELINE_ROOTS = ("curated", "extracted", "embeddings", "features")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema(path: Path) -> list[str] | dict[str, Any] | None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return next(csv.reader(stream), [])
    if suffix == ".json":
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
        sample = value[0] if isinstance(value, list) and value else value
        if isinstance(sample, dict):
            return sorted(sample)
        return {"type": type(value).__name__}
    if suffix == ".jsonl":
        with path.open(encoding="utf-8") as stream:
            sample = json.loads(next((line for line in stream if line.strip()), "null"))
        return sorted(sample) if isinstance(sample, dict) else {"type": type(sample).__name__}
    if suffix == ".npy":
        import numpy as np

        array = np.load(path, mmap_mode="r", allow_pickle=False)
        return {"dtype": str(array.dtype), "shape": list(array.shape)}
    return None


def build_manifest(repo_root: Path) -> dict[str, Any]:
    data_root = repo_root / "data"
    roots: dict[str, Any] = {}
    for name in BASELINE_ROOTS:
        root = data_root / name
        files = sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []
        entries = []
        schemas = {}
        aggregate = hashlib.sha256()
        for path in files:
            relative = path.relative_to(root).as_posix()
            file_hash = _sha256(path)
            aggregate.update(f"{relative}\0{file_hash}\n".encode())
            schema = _schema(path)
            entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_hash})
            if schema is not None:
                schemas[relative] = schema
        roots[name] = {
            "status": "available" if files else "missing_or_empty",
            "file_count": len(files),
            "total_bytes": sum(entry["bytes"] for entry in entries),
            "sha256": aggregate.hexdigest(),
            "schemas": schemas,
            "files": entries,
        }
    return {"schema_version": "1.0", "roots": roots}
