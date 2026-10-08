from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import gymnasium as gym
import numpy as np

from src.environment.matching_env import MatchingEnv
from src.features.feature_builder import validate_advisor_source

DEFAULT_TIMESTEPS = 2_000_000
SMOKE_TIMESTEPS = 16
CONTRACT_FIELDS = (
    "algorithm", "dataset_hash", "split_hash", "feature_hash",
    "environment_version", "capacity_policy_hash", "training_scope",
)

ROOT = Path(__file__).parents[2]
FEATURE_MANIFEST = ROOT / "data/features/feature_manifest_v2.json"
FEATURE_MATRIX = ROOT / "data/features/compatibility_matrix_v2.npy"


def _artifact_provenance() -> dict[str, str]:
    validate_advisor_source(ROOT)
    if not FEATURE_MANIFEST.exists() or not FEATURE_MATRIX.exists():
        raise FileNotFoundError("required feature provenance artifacts are missing")
    manifest = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    matrix_hash = hashlib.sha256(np.load(FEATURE_MATRIX, allow_pickle=False).tobytes()).hexdigest()
    if matrix_hash != manifest.get("matrix_sha256"):
        raise ValueError("feature matrix hash does not match its manifest")
    policy = "uniform-ceiling-experimental-v1"
    return {
        "dataset_hash": manifest["dataset_sha256"],
        "split_hash": manifest["split_sha256"],
        "feature_hash": matrix_hash,
        "capacity_policy_hash": hashlib.sha256(policy.encode()).hexdigest(),
    }


TOY_MATRIX = np.array([[0.9, 0.2], [0.1, 0.8]], dtype=np.float32)
TOY_HASH = hashlib.sha256(TOY_MATRIX.tobytes()).hexdigest()


@dataclass(frozen=True)
class TrainingConfig:
    algorithm: str
    timesteps: int = DEFAULT_TIMESTEPS
    seed: int = 42
    output_dir: Path = Path("outputs/checkpoints")
    dataset_hash: str = ""
    split_hash: str = ""
    feature_hash: str = ""
    environment_version: str = "matching-env-v2-real"
    capacity_policy_hash: str = ""
    smoke: bool = False
    training_scope: str = "curated-train"

    def __post_init__(self):
        if self.timesteps <= 0:
            raise ValueError("timesteps must be positive")
        provenance = ({name: TOY_HASH for name in ('dataset_hash', 'split_hash', 'feature_hash', 'capacity_policy_hash')}
                      if self.smoke else _artifact_provenance())
        for name, value in provenance.items():
            if not getattr(self, name):
                object.__setattr__(self, name, value)

    def with_smoke(self) -> TrainingConfig:
        return replace(self, timesteps=SMOKE_TIMESTEPS, smoke=True,
                       training_scope="synthetic-smoke", environment_version="matching-env-v2-smoke",
                       dataset_hash=TOY_HASH, split_hash=TOY_HASH, feature_hash=TOY_HASH,
                       capacity_policy_hash=TOY_HASH)

    def contract(self) -> dict[str, str]:
        return {field: str(getattr(self, field)) for field in CONTRACT_FIELDS}


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timesteps", type=int, default=DEFAULT_TIMESTEPS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/checkpoints"))
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--smoke", action="store_true")


def config_from_args(algorithm: str, args: argparse.Namespace) -> TrainingConfig:
    if args.smoke:
        return TrainingConfig(algorithm, SMOKE_TIMESTEPS, args.seed, args.output_dir,
                              smoke=True, training_scope="synthetic-smoke",
                              environment_version="matching-env-v2-smoke")
    config = TrainingConfig(algorithm, args.timesteps, args.seed, args.output_dir)
    return config


def build_environment(config: TrainingConfig):
    if config.smoke:
        scores, capacities = TOY_MATRIX.copy(), np.array([1, 1], dtype=np.int64)
    else:
        provenance = _artifact_provenance()
        if any(getattr(config, key) != value for key, value in provenance.items()):
            raise ValueError("training provenance no longer matches features")
        split_path = ROOT / 'data/curated/split_indices.json'
        if hashlib.sha256(split_path.read_bytes()).hexdigest() != config.split_hash:
            raise ValueError("split hash mismatch")
        split = json.loads(split_path.read_text(encoding='utf-8'))
        indices = split['indices']['train']
        if not indices or len(set(indices)) != len(indices):
            raise ValueError("train indices must be non-empty and unique")
        scores = np.load(FEATURE_MATRIX, allow_pickle=False)[indices]
        capacities = np.full(scores.shape[1], int(np.ceil(scores.shape[0] / scores.shape[1])), dtype=np.int64)
    env = MatchingEnv(scores, capacities)
    return gym.wrappers.TimeLimit(env, max_episode_steps=4 * env.n_students)


def count_invalid_proposals(model, env, *, masked: bool = False, recurrent: bool = False) -> int:
    observation, _ = env.reset()
    state, episode_start, invalid = None, True, 0
    done = False
    while not done:
        kwargs = {"deterministic": True}
        if masked:
            kwargs["action_masks"] = env.unwrapped.action_masks()
        if recurrent:
            kwargs.update(state=state, episode_start=[episode_start])
        action, state = model.predict(observation, **kwargs)
        observation, _, terminated, truncated, info = env.step(int(action))
        invalid += int(info.get("invalid_action", False))
        done = terminated or truncated
        episode_start = done
    return invalid


def run_manifest(config: TrainingConfig, *, completed_timesteps: int = 0, status: str = "configured") -> dict:
    values = asdict(config)
    values["output_dir"] = str(config.output_dir)
    values.update({
        "requested_timesteps": config.timesteps,
        "completed_timesteps": completed_timesteps,
        "status": status,
        "library_versions": {
            name: importlib.metadata.version(name)
            for name in ("stable-baselines3", "sb3-contrib", "gymnasium", "torch")
        },
        "invalid_proposals": 0,
        "quota_violations": 0,
        "capacity_policy": "uniform ceiling; experimental assumption",
        "observation_shape": list(build_environment(config).observation_space.shape),
        "action_count": int(build_environment(config).action_space.n),
    })
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return {**values, "config_hash": hashlib.sha256(canonical).hexdigest()}


def write_run_manifest(config: TrainingConfig, path: Path, **updates) -> dict:
    manifest = {**run_manifest(config), **updates}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
