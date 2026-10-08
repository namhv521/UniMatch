from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.serving import MatchingService, ServiceError
from src.serving.model_registry import ModelRecord, ModelRegistry

ROOT = Path(__file__).parents[2]


def test_registry_detects_legacy_toy_checkpoints_and_rejects_real_dataset() -> None:
    models = ModelRegistry(ROOT).catalog()
    full = {model["algorithm"]: model for model in models if not model["smoke"] and not model["research"]}

    assert {"ARS", "DQN", "MaskablePPO", "QRDQN", "RecurrentPPO", "TRPO"} <= set(full)
    assert all(model["status"] == "toy_unpromoted" for model in full.values())
    assert all(model["observation_shape"] == [6] for model in full.values())
    assert all(model["action_count"] == 2 for model in full.values())
    assert all(model["supported_datasets"] == ["sample-2x2", "sample-3x2"] for model in full.values())
    assert all(model["promoted"] is False for model in full.values())


def test_registry_marks_hash_mismatch_invalid(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "outputs/checkpoints"
    checkpoint_dir.mkdir(parents=True)
    source = ROOT / "outputs/checkpoints/dqn.zip"
    shutil.copy2(source, checkpoint_dir / source.name)
    manifest = json.loads((ROOT / "outputs/checkpoints/dqn.json").read_text(encoding="utf-8"))
    manifest["sha256"] = "0" * 64
    (checkpoint_dir / "dqn.json").write_text(json.dumps(manifest), encoding="utf-8")

    [model] = ModelRegistry(tmp_path).catalog()

    assert model["status"] == "invalid"
    assert model["reason"] == "checkpoint_hash_mismatch"
    assert model["supported_datasets"] == []


def _copy_current_research_contract(tmp_path: Path) -> tuple[Path, dict]:
    (tmp_path / "data/features").mkdir(parents=True)
    (tmp_path / "data/curated").mkdir(parents=True)
    shutil.copy2(ROOT / "data/features/feature_manifest_v2.json", tmp_path / "data/features/feature_manifest_v2.json")
    shutil.copy2(ROOT / "data/curated/split_indices.json", tmp_path / "data/curated/split_indices.json")
    source_manifest = min((ROOT / "outputs/research-real").glob("*.json"))
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    return source_manifest.parent / manifest["checkpoint"], manifest


def test_research_registry_rejects_manifest_when_live_feature_contract_changes(tmp_path: Path) -> None:
    checkpoint, manifest = _copy_current_research_contract(tmp_path)
    target = tmp_path / "outputs/research-real"
    target.mkdir(parents=True)
    shutil.copy2(checkpoint, target / checkpoint.name)
    (target / "candidate.json").write_text(json.dumps(manifest), encoding="utf-8")
    feature_path = tmp_path / "data/features/feature_manifest_v2.json"
    feature = json.loads(feature_path.read_text(encoding="utf-8"))
    feature["dataset_sha256"] = "f" * 64
    feature_path.write_text(json.dumps(feature), encoding="utf-8")

    [model] = ModelRegistry(tmp_path).catalog()

    assert model["status"] == "invalid"
    assert model["reason"] == "research_contract_mismatch"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"status": "configured"}, "research_checkpoint_state_mismatch"),
        ({"smoke": True}, "research_checkpoint_state_mismatch"),
        ({"requested_timesteps": 999999, "completed_timesteps": 10}, "research_checkpoint_state_mismatch"),
        ({"requested_timesteps": 1, "completed_timesteps": 1}, "research_checkpoint_steps_mismatch"),
    ],
)
def test_research_registry_requires_completed_manifest_and_matching_archive_steps(
    tmp_path: Path, changes: dict, reason: str
) -> None:
    checkpoint, manifest = _copy_current_research_contract(tmp_path)
    target = tmp_path / "outputs/research-real"
    target.mkdir(parents=True)
    shutil.copy2(checkpoint, target / checkpoint.name)
    manifest.update(changes)
    (target / "candidate.json").write_text(json.dumps(manifest), encoding="utf-8")

    [model] = ModelRegistry(tmp_path).catalog()

    assert model["status"] == "invalid"
    assert model["reason"] == reason


def test_resolve_prefers_highest_completed_timesteps_not_lexical_filename(tmp_path: Path) -> None:
    target = tmp_path / "outputs"
    target.mkdir(parents=True)
    records = []
    for name, timesteps in (("a-low", 100), ("z-high", 200)):
        manifest = target / f"{name}.json"
        manifest.write_text(json.dumps({"seed": 42, "completed_timesteps": timesteps}), encoding="utf-8")
        records.append(ModelRecord(
            "MaskablePPO", manifest, target / f"{name}.zip", False, "unpromoted_research", None,
            [114], 38, ["real-validation"], True,
        ))
    registry = ModelRegistry(tmp_path)
    registry._records = lambda: records

    record = registry.resolve("MaskablePPO", "real-validation", research=True, seed=42)

    assert record.manifest_path.stem == "z-high"


def test_real_dataset_uses_frozen_validation_mapping_without_pii() -> None:
    service = MatchingService(ROOT)
    dataset = service.dataset("real-validation")

    assert dataset["sample"] is False
    assert dataset["capacity_policy"] == "uniform-ceiling experimental; not official quota"
    assert len(dataset["students"]) == len(service.split['indices']['validation'])
    assert len(dataset["advisors"]) == 38
    assert len(dataset["scores"]) == len(service.split['indices']['validation'])
    assert len(dataset["scores"][0]) == 38
    assert dataset["students"][0]["id"].startswith("SV-VAL-")
    assert dataset["advisors"][0]["id"].startswith("GV-")
    serialized = json.dumps(dataset, ensure_ascii=False)
    assert "11181231" not in serialized
    assert "http" not in serialized.lower()
    assert len(service.dataset("real-train")["students"]) == len(service.split['indices']['train'])
    with pytest.raises(ServiceError, match="final holdout"):
        service.dataset("real-test")


@pytest.mark.parametrize("algorithm", ["hungarian", "greedy", "random"])
def test_real_baseline_trace_preserves_capacity_and_actual_loads(algorithm: str) -> None:
    service = MatchingService(ROOT)
    result = service.simulate("semantic", algorithm, "real-validation", seed=42)

    assert len(result["assignments"]) == len(service.split['indices']['validation'])
    assert result["metrics"]["quota_violations"] == 0
    assert result["provenance"]["capacity_policy"] == "uniform-ceiling experimental; not official quota"
    assert result["events"][-1]["loads_after"] == result["metrics"]["advisor_loads"]
    assert all(event["invalid_proposal"] is False for event in result["events"])


def test_old_toy_checkpoint_never_serves_real_dataset() -> None:
    with pytest.raises(ServiceError, match="not compatible with real-validation"):
        MatchingService(ROOT).simulate("rl", "DQN", "real-validation", seed=42)


def test_toy_checkpoint_runs_only_explicit_sample_with_unpromoted_banner() -> None:
    result = MatchingService(ROOT).simulate("rl", "DQN", "sample-2x2", seed=42)

    assert result["sample"] is True
    assert result["experimental"] is True
    assert "unpromoted" in result["banner"].lower()
    assert len(result["assignments"]) == 2
    assert result["metrics"]["quota_violations"] == 0


def test_invalid_rl_proposal_is_recorded_then_bounded_greedy_fallback(monkeypatch) -> None:
    class AlwaysFirstAdvisor:
        def predict(self, _observation, **_kwargs):
            return np.array([0]), None

    monkeypatch.setattr("src.serving.service.load_policy", lambda _record: AlwaysFirstAdvisor())

    result = MatchingService(ROOT).simulate("rl", "DQN", "sample-2x2", seed=42)

    assert len(result["events"]) == 3
    invalid, fallback = result["events"][1:]
    assert invalid["invalid_proposal"] is True
    assert invalid["loads_before"] == invalid["loads_after"] == [1, 0]
    assert invalid["reward"] == -2.0
    assert fallback["fallback"] is True
    assert fallback["advisor_index"] == 1
    assert fallback["loads_before"] == [1, 0]
    assert fallback["loads_after"] == [1, 1]


def test_recommendation_fits_train_and_returns_only_anonymous_evidence() -> None:
    result = MatchingService(ROOT).recommend("Ứng dụng xử lý ngôn ngữ tự nhiên", top_k=3)

    assert len(result["recommendations"]) == 3
    assert all(item["advisor_id"].startswith("GV-") for item in result["recommendations"])
    assert all(len(item["evidence_refs"]) == 1 for item in result["recommendations"])
    assert all(len(item["evidence_refs"][0]) == 64 for item in result["recommendations"])
    serialized = json.dumps(result, ensure_ascii=False)
    assert "advisor_name" not in serialized
    assert "http" not in serialized.lower()
