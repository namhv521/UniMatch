from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.features.feature_builder import validate_advisor_source


def _key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


@dataclass(frozen=True)
class ModelRecord:
    algorithm: str
    manifest_path: Path
    checkpoint_path: Path | None
    smoke: bool
    status: str
    reason: str | None
    observation_shape: list[int] | None
    action_count: int | None
    supported_datasets: list[str]
    research: bool

    def public(self) -> dict[str, object]:
        manifest = _read_manifest(self.manifest_path)
        return {
            "id": self.manifest_path.stem,
            "algorithm": self.algorithm,
            "seed": _read_seed(self.manifest_path),
            "smoke": self.smoke,
            "status": self.status,
            "reason": self.reason,
            "observation_shape": self.observation_shape,
            "action_count": self.action_count,
            "supported_datasets": self.supported_datasets,
            "promoted": False,
            "research": self.research,
            "requested_timesteps": manifest.get("requested_timesteps"),
            "completed_timesteps": manifest.get("completed_timesteps"),
            "training_scope": manifest.get("training_scope"),
        }


def _read_seed(path: Path) -> int | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("seed")
        return int(value) if value is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


class ModelRegistry:
    """Fail-closed inventory for checkpoint artifacts; it never promotes a model."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path(__file__).parents[2]
        self._signature: tuple[tuple[str, int, int], ...] | None = None
        self._cache: list[ModelRecord] = []

    def _records(self) -> list[ModelRecord]:
        directories = (
            (self.root / "outputs/checkpoints", False),
            (self.root / "outputs/research-real", True),
            (self.root / "outputs/research-filtered", True),
            (self.root / "outputs/research-current", True),
        )
        files = [
            path
            for directory, _research in directories
            if directory.is_dir()
            for pattern in ("*.json", "*.zip")
            for path in directory.glob(pattern)
        ]
        files.extend(
            path for path in (
                self.root / "data/curated/advisors.json",
                self.root / "data/curated/quality_report_v2.json",
                self.root / "data/features/feature_manifest_v2.json",
                self.root / "data/curated/split_indices.json",
                self.root / "data/curated/serving_contract.json",
            )
            if path.is_file()
        )
        signature = tuple(
            (str(path.relative_to(self.root)), path.stat().st_mtime_ns, path.stat().st_size)
            for path in sorted(files)
        )
        if signature == self._signature:
            return list(self._cache)
        records: list[ModelRecord] = []
        for directory, research in directories:
            if not directory.is_dir():
                continue
            for manifest_path in sorted(directory.glob("*.json")):
                records.append(self._inspect(manifest_path, research=research))
        self._signature = signature
        self._cache = records
        return list(records)

    def _inspect(self, manifest_path: Path, *, research: bool) -> ModelRecord:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            algorithm = str(manifest["algorithm"])
            checkpoint_name = str(manifest["checkpoint"])
            if Path(checkpoint_name).name != checkpoint_name:
                raise ValueError("unsafe_checkpoint_name")
            checkpoint = manifest_path.parent / checkpoint_name
            if not checkpoint.is_file():
                return self._invalid(algorithm, manifest_path, bool(manifest.get("smoke")), "checkpoint_missing", research)
            actual_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            if actual_hash != manifest.get("sha256"):
                return self._invalid(algorithm, manifest_path, bool(manifest.get("smoke")), "checkpoint_hash_mismatch", research)
            observation_shape, action_count, archive_steps = self._spaces(checkpoint)
            if observation_shape == [6] and action_count == 2 and not research:
                status = "toy_unpromoted"
                supported = ["sample-2x2", "sample-3x2"]
                reason = "checkpoint_space_is_toy_despite_manifest_provenance"
            elif observation_shape == [114] and action_count == 38 and research:
                contract = self._research_contract()
                contract_matches = contract is not None and all(
                    manifest.get(field) == value for field, value in contract.items()
                )
                completed = int(manifest.get("completed_timesteps", 0))
                requested = int(manifest.get("requested_timesteps", 0))
                state_matches = (
                    manifest.get("status") == "completed"
                    and manifest.get("smoke") is False
                    and requested > 0
                    and completed >= requested
                )
                if not state_matches:
                    status = "invalid"
                    supported = []
                    reason = "research_checkpoint_state_mismatch"
                elif archive_steps != completed:
                    status = "invalid"
                    supported = []
                    reason = "research_checkpoint_steps_mismatch"
                elif contract_matches and manifest.get("environment_version") == "matching-env-v2-real" and manifest.get("training_scope") == "curated-train":
                    status = "unpromoted_research"
                    supported = ["real-train", "real-validation"]
                    reason = "research_checkpoint_requires_explicit_unpromoted_mode"
                else:
                    status = "invalid"
                    supported = []
                    reason = "research_contract_mismatch"
            else:
                status = "invalid"
                supported = []
                reason = "unsupported_observation_or_action_space"
            return ModelRecord(
                algorithm, manifest_path, checkpoint, bool(manifest.get("smoke")), status, reason,
                observation_shape, action_count, supported, research,
            )
        except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError, zipfile.BadZipFile):
            return self._invalid(manifest_path.stem, manifest_path, False, "invalid_manifest_or_archive", research)

    @staticmethod
    def _spaces(checkpoint: Path) -> tuple[list[int], int, int]:
        with zipfile.ZipFile(checkpoint) as archive:
            data = json.loads(archive.read("data"))
        shape = [int(value) for value in data["observation_space"]["_shape"]]
        count = int(data["action_space"]["n"])
        steps = int(data.get("num_timesteps", -1))
        return shape, count, steps

    @staticmethod
    def _invalid(algorithm: str, manifest_path: Path, smoke: bool, reason: str, research: bool) -> ModelRecord:
        return ModelRecord(algorithm, manifest_path, None, smoke, "invalid", reason, None, None, [], research)

    def _research_contract(self) -> dict[str, str] | None:
        feature_path = self.root / "data/features/feature_manifest_v2.json"
        split_path = self.root / "data/curated/split_indices.json"
        try:
            validate_advisor_source(self.root)
            feature = json.loads(feature_path.read_text(encoding="utf-8"))
            split = json.loads(split_path.read_text(encoding="utf-8"))
            actual_split_hash = hashlib.sha256(split_path.read_bytes()).hexdigest()
            counts = {name: len(split["indices"][name]) for name in ("train", "validation", "test", "future")}
            contract_path = self.root / 'data/curated/serving_contract.json'
            expected_counts = (json.loads(contract_path.read_text(encoding='utf-8'))['split_counts']
                               if contract_path.is_file() else {'train':158, 'validation':21, 'test':21, 'future':20})
            if (
                split.get("schema_version") != "2.0"
                or feature.get("dataset_sha256") != split.get("dataset_sha256")
                or feature.get("split_sha256") != actual_split_hash
                or counts != expected_counts
            ):
                return None
            policy_hash = hashlib.sha256(b"uniform-ceiling-experimental-v1").hexdigest()
            return {
                "dataset_hash": str(feature["dataset_sha256"]),
                "split_hash": actual_split_hash,
                "feature_hash": str(feature["matrix_sha256"]),
                "capacity_policy_hash": policy_hash,
            }
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def catalog(self) -> list[dict[str, object]]:
        return [record.public() for record in self._records()]

    def resolve(self, algorithm: str, dataset: str, *, research: bool = False, seed: int | None = None) -> ModelRecord:
        matching = [
            record for record in self._records()
            if _key(record.algorithm) == _key(algorithm) and record.research is research and not record.smoke
            and (seed is None or _read_seed(record.manifest_path) == seed)
        ]
        if not matching:
            raise LookupError("model_unavailable")
        candidates = [
            record for record in matching
            if record.status != "invalid" and dataset in record.supported_datasets
        ]
        if not candidates:
            raise LookupError(f"model_not_compatible:{dataset}")
        return min(
            candidates,
            key=lambda record: (-_completed_timesteps(record.manifest_path), record.manifest_path.name),
        )


def _completed_timesteps(path: Path) -> int:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("completed_timesteps", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def _read_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_policy(record: ModelRecord):
    if record.checkpoint_path is None:
        raise ValueError("checkpoint is unavailable")
    normalized = _key(record.algorithm)
    if normalized == "dqn":
        from stable_baselines3 import DQN

        model_class = DQN
    else:
        from sb3_contrib import ARS, QRDQN, TRPO, MaskablePPO, RecurrentPPO

        model_class = {
            "ars": ARS,
            "maskableppo": MaskablePPO,
            "qrdqn": QRDQN,
            "recurrentppo": RecurrentPPO,
            "trpo": TRPO,
        }.get(normalized)
    if model_class is None:
        raise ValueError("unsupported model algorithm")
    model = model_class.load(record.checkpoint_path, device="cpu")
    expected_steps = _completed_timesteps(record.manifest_path)
    if int(model.num_timesteps) != expected_steps:
        raise ValueError("loaded model timesteps do not match checkpoint manifest")
    return model
