import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from scripts.audit_data import audit

ROOT = Path(__file__).parents[2]


def _json_hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ordered_hash(values):
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def _snapshot(root):
    curated = root / "data/curated"
    features = root / "data/features"
    excluded = root / "data/excluded/requested-five"
    cache = root / "data/cache"
    for path in (curated, features, excluded, cache):
        path.mkdir(parents=True)

    theses = [{"student_id": f"s{i}", "thesis_id": f"t{i}"} for i in range(4)]
    advisors = [
        {"advisor_id": "a0", "skill_text": "python", "profile_text": "python", "quota": None},
        {"advisor_id": "a1", "skill_text": "", "profile_text": "", "quota": None},
    ]
    splits = {
        "schema_version": "2.0",
        "student_ids": {name: [f"s{i}"] for i, name in enumerate(("train", "validation", "test", "future"))},
        "indices": {name: [i] for i, name in enumerate(("train", "validation", "test", "future"))},
    }
    matrix = np.arange(8, dtype=float).reshape(4, 2) / 8
    np.save(features / "compatibility_matrix_v2.npy", matrix)
    (curated / "theses.json").write_text(json.dumps(theses), encoding="utf-8")
    (curated / "advisors.json").write_text(json.dumps(advisors), encoding="utf-8")
    (curated / "split_indices.json").write_text(json.dumps(splits), encoding="utf-8")
    dataset_hash = _json_hash(theses)
    matrix_hash = hashlib.sha256(matrix.tobytes()).hexdigest()
    split_hash = hashlib.sha256((curated / "split_indices.json").read_bytes()).hexdigest()
    splits["dataset_sha256"] = dataset_hash
    (curated / "split_indices.json").write_text(json.dumps(splits), encoding="utf-8")
    split_hash = hashlib.sha256((curated / "split_indices.json").read_bytes()).hexdigest()
    manifest = {
        "matrix_shape": [4, 2],
        "matrix_sha256": matrix_hash,
        "dataset_sha256": dataset_hash,
        "split_sha256": split_hash,
    }
    contract = {
        **manifest,
        "student_order_sha256": _ordered_hash([row["student_id"] for row in theses]),
        "advisor_order_sha256": _ordered_hash([row["advisor_id"] for row in advisors]),
        "split_counts": {name: 1 for name in splits["indices"]},
    }
    (features / "feature_manifest_v2.json").write_text(json.dumps(manifest), encoding="utf-8")
    (curated / "serving_contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (excluded / "failure_report_original.json").write_text(
        json.dumps([{"source": "bad-source.json", "error": "ValidationError", "detail": "missing title"}]),
        encoding="utf-8",
    )
    (cache / "large-cache.npy").write_bytes(b"not a numpy file and must not be loaded")
    return splits, matrix


def _refresh_split_contract(root, splits):
    curated = root / "data/curated"
    features = root / "data/features"
    (curated / "split_indices.json").write_text(json.dumps(splits), encoding="utf-8")
    digest = hashlib.sha256((curated / "split_indices.json").read_bytes()).hexdigest()
    for path in (features / "feature_manifest_v2.json", curated / "serving_contract.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["split_sha256"] = digest
        path.write_text(json.dumps(value), encoding="utf-8")


def test_audit_separates_non_serving_errors_exclusions_and_warnings(tmp_path):
    _snapshot(tmp_path)
    malformed = tmp_path / "data/raw/tên file lỗi có khoảng trắng.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{", encoding="utf-8")
    output = tmp_path / "outputs/audit.json"

    report = audit(tmp_path, output=output)

    assert report["snapshot_usable"] is True
    assert report["active_snapshot_blockers"] == []
    assert [row["path"] for row in report["parse_errors"]] == [
        "data/raw/tên file lỗi có khoảng trắng.json"
    ]
    assert report["excluded_known_source_failures"]["count"] == 1
    assert report["excluded_known_source_failures"]["records"][0]["source"] == "bad-source.json"
    assert report["counts"]["unchecked_cache_files"] == 1
    assert report["counts"]["scanned_files"] + report["counts"]["unchecked_files"] == report["counts"]["total_files"]
    assert {warning["code"] for warning in report["warnings"]} >= {"advisor_missing_text", "advisor_missing_quota"}
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_audit_rejects_overlapping_active_split(tmp_path):
    splits, _ = _snapshot(tmp_path)
    splits["indices"]["validation"] = [0]
    splits["student_ids"]["validation"] = ["s0"]
    _refresh_split_contract(tmp_path, splits)

    report = audit(tmp_path)

    assert report["snapshot_usable"] is False
    assert any(row["code"] == "split_overlap" for row in report["active_snapshot_blockers"])


def test_audit_rejects_nonfinite_active_matrix(tmp_path):
    _, matrix = _snapshot(tmp_path)
    matrix[0, 0] = np.nan
    np.save(tmp_path / "data/features/compatibility_matrix_v2.npy", matrix)
    digest = hashlib.sha256(matrix.tobytes()).hexdigest()
    for path in (
        tmp_path / "data/features/feature_manifest_v2.json",
        tmp_path / "data/curated/serving_contract.json",
    ):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["matrix_sha256"] = digest
        path.write_text(json.dumps(value), encoding="utf-8")

    report = audit(tmp_path)

    assert report["snapshot_usable"] is False
    assert any(row["code"] == "nonfinite_array" for row in report["active_snapshot_blockers"])


def test_cli_returns_zero_for_non_serving_parse_errors(tmp_path):
    _snapshot(tmp_path)
    bad = tmp_path / "data/raw/bad.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{", encoding="utf-8")
    output = tmp_path / "audit.json"

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_data.py"), "--root", str(tmp_path), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["snapshot_usable"] is True
    assert output.is_file()


def test_valid_json_with_wrong_entity_type_returns_blocker(tmp_path):
    _snapshot(tmp_path)
    (tmp_path / 'data/curated/theses.json').write_text('[null]')
    report = audit(tmp_path)
    assert report['snapshot_usable'] is False
    assert any(row['code'] == 'entity_shape' for row in report['active_snapshot_blockers'])


def test_valid_json_with_wrong_split_type_returns_blocker(tmp_path):
    _snapshot(tmp_path)
    (tmp_path / 'data/curated/split_indices.json').write_text('[]')
    report = audit(tmp_path)
    assert report['snapshot_usable'] is False
    assert any(row['code'] == 'split_shape' for row in report['active_snapshot_blockers'])


def test_current_snapshot_is_usable_and_report_is_written():
    output = ROOT / "outputs/data_quality/audit-current.json"

    report = audit(ROOT, output=output)

    assert report["snapshot_usable"] is True
    assert report["serving_checks"]["matching_service"] == "passed"
    assert report["serving_checks"]["load_split"] == ["train", "validation", "test", "future"]
    assert output.is_file()
