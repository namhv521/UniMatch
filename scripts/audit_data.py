"""Read-only structural and serving-contract audit for the repository data tree."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


ACTIVE_FILES = {
    "data/curated/advisors.json",
    "data/curated/serving_contract.json",
    "data/curated/split_indices.json",
    "data/curated/theses.json",
    "data/features/compatibility_matrix_v2.npy",
    "data/features/feature_manifest_v2.json",
}
SPLITS = ("train", "validation", "test", "future")
EXCLUDED_FAILURES = "data/excluded/requested-five/failure_report_original.json"


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _check_file(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open(encoding="utf-8") as handle:
            json.load(handle)
    elif suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid JSONL line {line_number}: {exc.msg}") from exc
    elif suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for _ in csv.reader(handle):
                pass
    elif suffix in {".npy", ".npz"}:
        value = np.load(path, allow_pickle=False, mmap_mode="r" if suffix == ".npy" else None)
        try:
            arrays = [value[key] for key in value.files] if isinstance(value, np.lib.npyio.NpzFile) else [value]
            for array in arrays:
                if np.issubdtype(array.dtype, np.number) and not np.isfinite(array).all():
                    raise ValueError("array contains non-finite values")
        finally:
            if isinstance(value, np.lib.npyio.NpzFile):
                value.close()
    elif suffix == ".pdf":
        size = path.stat().st_size
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("missing PDF header")
            handle.seek(max(0, size - 4096))
            if b"%%EOF" not in handle.read():
                raise ValueError("missing PDF EOF marker")
    elif suffix in {".zip", ".docx"}:
        with zipfile.ZipFile(path) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise ValueError(f"corrupt ZIP member: {corrupt_member}")
    else:
        raise LookupError("format has no bounded safe structural checker")


def _scan_tree(root: Path) -> tuple[dict[str, int], list[dict[str, str]], list[dict[str, str]]]:
    data_root = root / "data"
    parse_errors: list[dict[str, str]] = []
    unchecked: list[dict[str, str]] = []
    formats: Counter[str] = Counter()
    total = scanned = cache_files = symlink_files = 0

    if not data_root.is_dir():
        return {
            "total_files": 0,
            "scanned_files": 0,
            "unchecked_files": 0,
            "unchecked_cache_files": 0,
            "unchecked_symlinks": 0,
        }, parse_errors, unchecked

    for directory, names, filenames in os.walk(data_root, followlinks=False):
        current = Path(directory)
        for name in list(names):
            candidate = current / name
            if candidate.is_symlink():
                names.remove(name)
                unchecked.append({"path": _relative(candidate, root), "reason": "symlink_directory_not_followed"})
                total += 1
                symlink_files += 1
        for name in filenames:
            path = current / name
            relative = _relative(path, root)
            total += 1
            formats[path.suffix.lower() or "<none>"] += 1
            if path.is_symlink():
                unchecked.append({"path": relative, "reason": "symlink_not_followed"})
                symlink_files += 1
                continue
            if "cache" in path.relative_to(data_root).parts:
                unchecked.append({"path": relative, "reason": "non_serving_cache_not_loaded"})
                cache_files += 1
                continue
            try:
                _check_file(path)
                scanned += 1
            except LookupError as exc:
                unchecked.append({"path": relative, "reason": str(exc)})
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError, csv.Error, zipfile.BadZipFile) as exc:
                scanned += 1
                parse_errors.append({"path": relative, "kind": path.suffix.lower() or "unknown", "error": str(exc)})

    counts = {
        "total_files": total,
        "scanned_files": scanned,
        "unchecked_files": len(unchecked),
        "unchecked_cache_files": cache_files,
        "unchecked_symlinks": symlink_files,
        "files_by_extension": dict(sorted(formats.items())),
    }
    return counts, parse_errors, unchecked


def _block(blockers: list[dict[str, str]], code: str, detail: str) -> None:
    if not any(row["code"] == code and row["detail"] == detail for row in blockers):
        blockers.append({"code": code, "detail": detail})


def _validate_active_snapshot(root: Path) -> tuple[list[dict[str, str]], dict[str, Any], list[dict[str, Any]]]:
    blockers: list[dict[str, str]] = []
    checks: dict[str, Any] = {"matching_service": "failed", "load_split": []}
    warnings: list[dict[str, Any]] = []
    curated = root / "data/curated"
    features = root / "data/features"

    try:
        from src.serving.service import MatchingService

        MatchingService(root)
        checks["matching_service"] = "passed"
    except Exception as exc:  # noqa: BLE001 - audit reports arbitrary serving initialization failures
        _block(blockers, "matching_service", str(exc))

    try:
        from src.evaluation.benchmark import load_split

        for split in SPLITS:
            load_split(root, split)
            checks["load_split"].append(split)
    except Exception as exc:  # noqa: BLE001 - audit reports failures across all snapshot loaders
        _block(blockers, "load_split", str(exc))

    try:
        theses = json.loads((curated / "theses.json").read_text(encoding="utf-8"))
        advisors = json.loads((curated / "advisors.json").read_text(encoding="utf-8"))
        split_data = json.loads((curated / "split_indices.json").read_text(encoding="utf-8"))
        matrix = np.load(features / "compatibility_matrix_v2.npy", allow_pickle=False)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _block(blockers, "active_snapshot_read", str(exc))
        return blockers, checks, warnings

    if not isinstance(theses, list) or not isinstance(advisors, list):
        _block(blockers, "entity_shape", "theses.json and advisors.json must contain arrays")
        return blockers, checks, warnings
    if any(not isinstance(row, dict) for row in theses + advisors):
        _block(blockers, 'entity_shape', 'every student and advisor must be an object')
        return blockers, checks, warnings
    if not isinstance(split_data, dict):
        _block(blockers, 'split_shape', 'split_indices.json must contain an object')
        return blockers, checks, warnings

    student_ids = [str(row.get("student_id", "")) for row in theses]
    advisor_ids = [str(row.get("advisor_id", "")) for row in advisors]
    for label, values in (("student", student_ids), ("advisor", advisor_ids)):
        if "" in values:
            _block(blockers, f"missing_{label}_id", f"one or more {label} IDs are empty")
        if len(values) != len(set(values)):
            _block(blockers, f"duplicate_{label}_id", f"duplicate {label} IDs")

    expected_shape = (len(theses), len(advisors))
    if matrix.shape != expected_shape:
        _block(blockers, "matrix_shape", f"matrix shape {matrix.shape} != {expected_shape}")
    if not np.issubdtype(matrix.dtype, np.number) or not np.isfinite(matrix).all():
        _block(blockers, "nonfinite_array", "active compatibility matrix must be finite numeric data")

    indices_by_split = split_data.get("indices", {})
    ids_by_split = split_data.get("student_ids", {})
    if not isinstance(indices_by_split, dict) or not isinstance(ids_by_split, dict):
        _block(blockers, 'split_shape', 'indices and student_ids must contain objects')
        return blockers, checks, warnings
    flattened: list[int] = []
    for split in SPLITS:
        indices = indices_by_split.get(split)
        mapped_ids = ids_by_split.get(split)
        if not isinstance(indices, list) or not isinstance(mapped_ids, list):
            _block(blockers, "split_missing", f"missing {split} indices or student IDs")
            continue
        if any(type(index) is not int or index < 0 or index >= len(theses) for index in indices):
            _block(blockers, "split_bounds", f"out-of-range index inside {split}")
            continue
        if len(indices) != len(set(indices)):
            _block(blockers, "split_duplicate_index", f"duplicate index inside {split}")
        if [student_ids[index] for index in indices] != [str(value) for value in mapped_ids]:
            _block(blockers, "split_id_mapping", f"ordered student mapping differs for {split}")
        flattened.extend(indices)
    if len(flattened) != len(set(flattened)):
        _block(blockers, "split_overlap", "student indices overlap across partitions")
    if set(flattened) != set(range(len(theses))):
        _block(blockers, "split_incomplete", "partitions do not cover every thesis exactly once")

    missing_text = sum(not str(row.get("profile_text") or row.get('skill_text') or "").strip() for row in advisors)
    missing_quota = sum(row.get("quota") is None for row in advisors)
    if missing_text:
        warnings.append({"code": "advisor_missing_text", "count": missing_text})
    if missing_quota:
        warnings.append({"code": "advisor_missing_quota", "count": missing_quota})
    return blockers, checks, warnings


def _excluded_failures(root: Path) -> dict[str, Any]:
    path = root / EXCLUDED_FAILURES
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            records = []
    except (OSError, json.JSONDecodeError, UnicodeError):
        records = []
    return {"path": EXCLUDED_FAILURES, "count": len(records), "records": records}


def audit(root: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    """Audit data without modifying it; only an optional JSON report is written."""
    root = Path(root).resolve()
    counts, parse_errors, unchecked = _scan_tree(root)
    blockers, serving_checks, warnings = _validate_active_snapshot(root)
    for error in parse_errors:
        if error["path"] in ACTIVE_FILES:
            _block(blockers, "active_file_parse_error", f'{error["path"]}: {error["error"]}')
    if not (root / "data").is_dir():
        _block(blockers, "data_directory_missing", "data directory does not exist")

    report: dict[str, Any] = {
        "root": str(root),
        "snapshot_usable": not blockers,
        "active_snapshot_blockers": blockers,
        "parse_errors": parse_errors,
        "warnings": warnings,
        "excluded_known_source_failures": _excluded_failures(root),
        "serving_checks": serving_checks,
        "counts": counts,
        "unchecked": unchecked,
    }
    if output is not None:
        target = Path(output)
        if not target.is_absolute():
            target = root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = audit(args.root, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["snapshot_usable"] else 1


if __name__ == "__main__":
    sys.exit(main())
