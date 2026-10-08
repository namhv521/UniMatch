from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from src.baselines.greedy import greedy_assignment
from src.baselines.hungarian import hungarian_assignment
from src.baselines.random import random_assignment
from src.environment.matching_env import MatchingEnv
from src.environment.reward import matching_reward
from src.evaluation.metrics import load_variance, mean_compatibility, quota_violations
from src.features.feature_builder import FeatureBuilder, validate_advisor_source

from .model_registry import ModelRegistry, load_policy

MATRIX_SHA256 = "eb284ebccaf438633c2bb956ebff20b7e5e83b4ef8baf385dd5087c09ba764a6"
STUDENT_ORDER_SHA256 = "3fcf6cdd66e758a7be265054d8029fc84f1b93e574b221469d6e16978766d026"
ADVISOR_ORDER_SHA256 = "b095d1871cef51f7b82eb30762fcc54812bf79e63dee28f9efece17165033ef7"
CAPACITY_POLICY = "uniform-ceiling experimental; not official quota"


class ServiceError(ValueError):
    pass


def _json_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _ordered_hash(values: list[str]) -> str:
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class MatchingService:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path(__file__).parents[2]
        self.registry = ModelRegistry(self.root)
        self._load_artifacts()
        self._builder: FeatureBuilder | None = None

    def _load_artifacts(self) -> None:
        curated = self.root / "data/curated"
        feature_root = self.root / "data/features"
        try:
            self.theses = json.loads((curated / "theses.json").read_text(encoding="utf-8"))
            self.advisors = json.loads((curated / "advisors.json").read_text(encoding="utf-8"))
            self.split = json.loads((curated / "split_indices.json").read_text(encoding="utf-8"))
            self.feature_manifest = json.loads((feature_root / "feature_manifest_v2.json").read_text(encoding="utf-8"))
            self.matrix = np.load(feature_root / "compatibility_matrix_v2.npy", allow_pickle=False)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ServiceError("required serving artifacts are unavailable") from exc

        try:
            validate_advisor_source(self.root, required=len(self.advisors) != 2)
        except ValueError as exc:
            raise ServiceError(str(exc)) from exc

        matrix_hash = hashlib.sha256(self.matrix.tobytes(order="C")).hexdigest()
        dataset_hash = _json_hash(self.theses)
        split_hash = hashlib.sha256((curated / "split_indices.json").read_bytes()).hexdigest()
        student_order_hash = _ordered_hash([row["student_id"] for row in self.theses])
        advisor_order_hash = _ordered_hash([row["advisor_id"] for row in self.advisors])
        expected = self.feature_manifest
        contract_path = curated / 'serving_contract.json'
        contract = json.loads(contract_path.read_text(encoding='utf-8')) if contract_path.is_file() else {
            'matrix_sha256': MATRIX_SHA256,
            'dataset_sha256': expected.get('dataset_sha256'),
            'split_sha256': expected.get('split_sha256'),
            'student_order_sha256': STUDENT_ORDER_SHA256,
            'advisor_order_sha256': ADVISOR_ORDER_SHA256,
            'split_counts': {'train': 158, 'validation': 21, 'test': 21, 'future': 20},
        }
        checks = (
            self.split.get("schema_version") == "2.0",
            self.matrix.shape == (len(self.theses), len(self.advisors)),
            list(self.matrix.shape) == expected.get("matrix_shape"),
            matrix_hash == expected.get("matrix_sha256") == contract.get('matrix_sha256'),
            dataset_hash == expected.get("dataset_sha256") == self.split.get("dataset_sha256"),
            dataset_hash == contract.get('dataset_sha256'),
            split_hash == expected.get("split_sha256") == contract.get('split_sha256'),
            student_order_hash == contract.get('student_order_sha256'),
            advisor_order_hash == contract.get('advisor_order_sha256'),
            {name: len(self.split.get("indices", {}).get(name, [])) for name in ("train", "validation", "test", "future")}
            == contract.get('split_counts'),
        )
        if not all(checks):
            raise ServiceError("serving artifacts failed hash, dimension, split, or ordered mapping validation")
        self.provenance = {
            "dataset_sha256": dataset_hash,
            "feature_sha256": matrix_hash,
            "split_sha256": split_hash,
            "student_order_sha256": student_order_hash,
            "advisor_order_sha256": advisor_order_hash,
            "advisor_content_sha256": _json_hash(self.advisors),
        }

    @staticmethod
    def _sample(name: str) -> dict[str, object]:
        if name == "sample-2x2":
            scores = [[0.9, 0.2], [0.1, 0.8]]
            capacities = [1, 1]
        elif name == "sample-3x2":
            scores = [[0.9, 0.3], [0.4, 0.95], [0.8, 0.7]]
            capacities = [2, 1]
        else:
            raise ServiceError("unknown dataset")
        return {
            "id": name,
            "sample": True,
            "students": [{"id": f"SV{i + 1:02}", "label": f"Sinh viên {i + 1:02}"} for i in range(len(scores))],
            "advisors": [
                {"id": "GV-A", "label": "Giảng viên A", "capacity": capacities[0]},
                {"id": "GV-B", "label": "Giảng viên B", "capacity": capacities[1]},
            ],
            "scores": scores,
            "capacity_policy": "fictional sample capacities",
            "provenance": {"sample": "DESIGN.md sample; not project evaluation"},
        }

    def _real_split(self, split_name: str) -> dict[str, object]:
        if split_name not in {"train", "validation", "test"}:
            raise ServiceError("unknown dataset")
        indices = self.split["indices"][split_name]
        capacity = math.ceil(len(indices) / len(self.advisors))
        split_label = {"train": "TRAIN", "validation": "VAL", "test": "TEST"}[split_name]
        return {
            "id": f"real-{split_name}",
            "sample": False,
            "students": [
                {"id": f"SV-{split_label}-{position + 1:03}", "label": f"Sinh viên {split_name} {position + 1:03}"}
                for position in range(len(indices))
            ],
            "advisors": [
                {"id": f"GV-{position + 1:03}", "label": f"Giảng viên {position + 1:03}", "capacity": capacity}
                for position in range(len(self.advisors))
            ],
            "scores": self.matrix[indices].tolist(),
            "capacity_policy": CAPACITY_POLICY,
            "provenance": dict(self.provenance),
        }

    def dataset(self, name: str) -> dict[str, object]:
        if name == "real-test":
            raise ServiceError("final holdout is locked; use offline frozen-selection evaluation")
        if name.startswith("real-"):
            return self._real_split(name.removeprefix("real-"))
        return self._sample(name)

    def catalog(self) -> dict[str, object]:
        quality_path = self.root / "data/curated/quality_report_v2.json"
        quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {"ready": False}
        if 'input_files' in quality:
            fresh = all(
                (self.root / path).is_file()
                and hashlib.sha256((self.root / path).read_bytes()).hexdigest() == digest
                for path, digest in quality['input_files'].items()
            )
            quality = {**quality, 'ready': bool(quality.get('ready')) and fresh}
        return {
            "datasets": [
                {"id": "sample-2x2", "sample": True},
                {"id": "sample-3x2", "sample": True},
                {"id": "real-train", "sample": False, "capacity_policy": CAPACITY_POLICY},
                {"id": "real-validation", "sample": False, "capacity_policy": CAPACITY_POLICY},
            ],
            "models": self.registry.catalog(),
            "baselines": ["hungarian", "greedy", "random"],
            "modes": [
                {"id": "semantic", "available": True},
                {"id": "non_rl", "available": False, "reason": "trained non-RL artifact is missing"},
                {"id": "rl", "available": True, "scope": "toy samples only; unpromoted"},
                {"id": "rl_research", "available": False, "scope": "explicit unpromoted real-data research only"},
            ],
            "quality": {"ready": bool(quality.get("ready")), "scope": quality.get("scope", "unverified")},
        }

    def simulate(self, mode: str, algorithm: str, dataset: str, seed: int = 42) -> dict[str, object]:
        data = self.dataset(dataset)
        scores = np.asarray(data["scores"], dtype=float)
        capacities = np.asarray([row["capacity"] for row in data["advisors"]], dtype=int)
        normalized = algorithm.lower()
        if mode == "non_rl":
            raise ServiceError("trained non-RL artifact is unavailable")
        if mode == "semantic":
            if normalized == "hungarian":
                assigned = hungarian_assignment(scores, capacities)
            elif normalized == "greedy":
                assigned = greedy_assignment(scores, capacities)
            elif normalized == "random":
                assigned = random_assignment(len(scores), capacities, seed=seed)
            else:
                raise ServiceError("unsupported baseline algorithm")
            return self._baseline_result(data, normalized, scores, capacities, assigned)
        if mode not in {"rl", "rl_research"}:
            raise ServiceError("unsupported mode")
        research = mode == "rl_research"
        try:
            record = self.registry.resolve(algorithm, dataset, research=research, seed=seed)
        except LookupError as exc:
            detail = str(exc)
            if detail.startswith("model_not_compatible"):
                raise ServiceError(f"{algorithm} is not compatible with {dataset}") from exc
            raise ServiceError("requested model is unavailable") from exc
        return self._rl_result(data, scores, capacities, record)

    def _baseline_result(self, data, algorithm, scores, capacities, assigned) -> dict[str, object]:
        loads = np.zeros(len(capacities), dtype=int)
        events = []
        assignments = []
        for student_index, advisor_index in enumerate(np.asarray(assigned, dtype=int)):
            before = loads.copy()
            loads[advisor_index] += 1
            score = float(scores[student_index, advisor_index])
            reward = matching_reward(score, before, loads)
            event = self._event(data, len(events), student_index, int(advisor_index), score, reward, before, loads, capacities)
            events.append(event)
            assignments.append(self._assignment(data, student_index, int(advisor_index), score))
        return self._result(data, algorithm, assignments, events, scores, capacities, assigned)

    def _rl_result(self, data, scores, capacities, record) -> dict[str, object]:
        env = MatchingEnv(scores.astype(np.float32), capacities.astype(np.int64))
        model = load_policy(record)
        observation, _ = env.reset(seed=_read_seed(record.manifest_path) or 42)
        state = None
        assignments, events = [], []
        max_events = 2 * len(scores)
        while env.student_index < len(scores) and len(events) < max_events:
            student_index = env.student_index
            kwargs: dict[str, object] = {"deterministic": True}
            normalized = "".join(character for character in record.algorithm.lower() if character.isalnum())
            if normalized == "maskableppo":
                kwargs["action_masks"] = env.action_masks()
            if normalized == "recurrentppo":
                kwargs.update(state=state, episode_start=np.array([student_index == 0]))
            action, state = model.predict(observation, **kwargs)
            advisor_index = int(np.asarray(action).reshape(-1)[0])
            before = env.loads.copy()
            observation, reward, _, _, info = env.step(advisor_index)
            if info["invalid_action"]:
                events.append(self._event(
                    data, len(events), student_index, advisor_index, float(scores[student_index, advisor_index]),
                    float(reward), before, env.loads.copy(), capacities, invalid=True,
                    explanation="Model proposed an advisor with no remaining capacity.",
                ))
                feasible = np.flatnonzero(env.action_masks())
                advisor_index = int(feasible[np.argmax(scores[student_index, feasible])])
                before = env.loads.copy()
                observation, reward, _, _, _ = env.step(advisor_index)
                fallback = True
            else:
                fallback = False
            score = float(scores[student_index, advisor_index])
            events.append(self._event(
                data, len(events), student_index, advisor_index, score, float(reward), before,
                env.loads.copy(), capacities, fallback=fallback,
                explanation="Explicit greedy fallback after invalid proposal." if fallback else "Action emitted by checkpoint.",
            ))
            assignments.append(self._assignment(data, student_index, advisor_index, score))
        if env.student_index != len(scores):
            raise ServiceError("model simulation exceeded bounded event limit")
        assigned = np.asarray([row["advisor_index"] for row in assignments], dtype=int)
        result = self._result(data, record.algorithm, assignments, events, scores, capacities, assigned)
        result.update({
            "experimental": True,
            "banner": "UNPROMOTED research simulation; not a production or final evaluation result",
            "model_version": hashlib.sha256(record.checkpoint_path.read_bytes()).hexdigest() if record.checkpoint_path else None,
        })
        return result

    @staticmethod
    def _assignment(data, student_index: int, advisor_index: int, score: float) -> dict[str, object]:
        return {
            "student_id": data["students"][student_index]["id"],
            "advisor_id": data["advisors"][advisor_index]["id"],
            "student_index": student_index,
            "advisor_index": advisor_index,
            "score": score,
        }

    @staticmethod
    def _event(
        data, step, student_index, advisor_index, score, reward, before, after, capacities,
        *, invalid=False, fallback=False, explanation="Assignment applied with capacity validation.",
    ) -> dict[str, object]:
        return {
            "step": step,
            "student_id": data["students"][student_index]["id"],
            "advisor_id": data["advisors"][advisor_index]["id"],
            "student_index": student_index,
            "advisor_index": advisor_index,
            "score": score,
            "reward": reward,
            "loads_before": np.asarray(before, dtype=int).tolist(),
            "loads_after": np.asarray(after, dtype=int).tolist(),
            "capacities": np.asarray(capacities, dtype=int).tolist(),
            "invalid_proposal": invalid,
            "fallback": fallback,
            "explanation": explanation,
        }

    def _result(self, data, algorithm, assignments, events, scores, capacities, assigned) -> dict[str, object]:
        loads = np.bincount(np.asarray(assigned, dtype=int), minlength=len(capacities))
        return {
            "assignments": assignments,
            "events": events,
            "metrics": {
                "mean_compatibility": mean_compatibility(scores, assigned),
                "load_variance": load_variance(assigned, len(capacities)),
                "quota_violations": quota_violations(assigned, capacities),
                "invalid_proposals": sum(bool(event["invalid_proposal"]) for event in events),
                "advisor_loads": loads.tolist(),
            },
            "model_version": f"baseline-{algorithm}-v1",
            "data_version": self.provenance["dataset_sha256"] if not data["sample"] else data["id"],
            "provenance": {**data["provenance"], "capacity_policy": data["capacity_policy"]},
            "sample": data["sample"],
        }

    def recommend(self, title: str, top_k: int) -> dict[str, object]:
        if not title.strip():
            raise ServiceError("title must not be blank")
        if self._builder is None:
            train = self.split["indices"]["train"]
            student_texts = [row.get("feature_text") or row.get("thesis_title", "") for row in self.theses]
            advisor_texts = [row.get("profile_text") or row.get("skill_text") or "" for row in self.advisors]
            self._builder = FeatureBuilder().fit([student_texts[index] for index in train], advisor_texts)
        advisor_texts = [row.get("profile_text") or row.get("skill_text") or "" for row in self.advisors]
        scores, _ = self._builder.compatibility([title], advisor_texts)
        ranking = np.argsort(-scores[0])[:top_k]
        recommendations = []
        for index in ranking:
            evidence = hashlib.sha256(
                f"{self.provenance['dataset_sha256']}:{self.advisors[int(index)]['advisor_id']}".encode()
            ).hexdigest()
            recommendations.append({
                "advisor_id": f"GV-{int(index) + 1:03}",
                "label": f"Giảng viên {int(index) + 1:03}",
                "compatibility_score": float(scores[0, index]),
                "evidence_refs": [evidence],
            })
        return {
            "recommendations": recommendations,
            "model_version": "tfidf-feature-builder-v1",
            "data_version": self.provenance["dataset_sha256"],
            "provenance": dict(self.provenance),
        }


def _read_seed(path: Path) -> int | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("seed")
        return int(value) if value is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
