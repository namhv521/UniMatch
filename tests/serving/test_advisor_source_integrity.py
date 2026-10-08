from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.features.feature_builder import validate_advisor_source
from src.serving import MatchingService, ServiceError
from src.serving.model_registry import ModelRegistry

ROOT = Path(__file__).parents[2]


def _copy_data(root: Path) -> None:
    shutil.copytree(ROOT / "data/curated", root / "data/curated")
    shutil.copytree(ROOT / "data/features", root / "data/features")


def _stale_advisor_source(root: Path) -> None:
    path = root / "data/curated/advisors.json"
    advisors = json.loads(path.read_text(encoding="utf-8"))
    advisors[0]["profile_text"] += " stale edit"
    path.write_text(json.dumps(advisors, ensure_ascii=False), encoding="utf-8")


def test_optional_synthetic_source_allows_missing_report_but_validates_one_if_present(tmp_path: Path) -> None:
    assert validate_advisor_source(tmp_path, required=False) is None
    quality = tmp_path / "data/curated/quality_report_v2.json"
    quality.parent.mkdir(parents=True)
    quality.write_text(json.dumps({"input_files": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="advisor source"):
        validate_advisor_source(tmp_path, required=False)


def test_service_rejects_real_advisor_source_changed_after_quality_report(tmp_path: Path) -> None:
    _copy_data(tmp_path)
    _stale_advisor_source(tmp_path)

    with pytest.raises(ServiceError, match="advisor source"):
        MatchingService(tmp_path)


def test_training_rejects_real_advisor_source_changed_after_quality_report(tmp_path: Path, monkeypatch) -> None:
    from src.rl import training

    _copy_data(tmp_path)
    _stale_advisor_source(tmp_path)
    monkeypatch.setattr(training, "ROOT", tmp_path)
    monkeypatch.setattr(training, "FEATURE_MANIFEST", tmp_path / "data/features/feature_manifest_v2.json")
    monkeypatch.setattr(training, "FEATURE_MATRIX", tmp_path / "data/features/compatibility_matrix_v2.npy")

    with pytest.raises(ValueError, match="advisor source"):
        training._artifact_provenance()


def test_registry_invalidates_cache_when_advisor_source_changes(tmp_path: Path) -> None:
    _copy_data(tmp_path)
    source_manifest = next((ROOT / "outputs/research-current").glob("*.json"))
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    target = tmp_path / "outputs/research-current"
    target.mkdir(parents=True)
    shutil.copy2(source_manifest.parent / manifest["checkpoint"], target / manifest["checkpoint"])
    shutil.copy2(source_manifest, target / source_manifest.name)
    registry = ModelRegistry(tmp_path)

    [before] = registry.catalog()
    _stale_advisor_source(tmp_path)
    [after] = registry.catalog()

    assert before["status"] == "unpromoted_research"
    assert after["status"] == "invalid"
    assert after["reason"] == "research_contract_mismatch"
