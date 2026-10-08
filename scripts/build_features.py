import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data_pipeline.split import split_temporally
from src.features.feature_builder import FeatureBuilder


def main() -> None:
    root = Path(__file__).parents[1]
    curated = root / "data/curated"
    theses = json.loads((curated / "theses.json").read_text(encoding="utf-8"))
    advisors = json.loads((curated / "advisors.json").read_text(encoding="utf-8"))
    stable_split = split_temporally(theses)
    split_lookup = {student_id: name for name, ids in stable_split.items() for student_id in ids}
    split_indices = {
        name: [index for index, row in enumerate(theses) if split_lookup[row["student_id"]] == name]
        for name in stable_split
    }
    dataset_hash = hashlib.sha256(
        json.dumps(theses, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    split_path = curated / "split_indices.json"
    legacy = json.loads(split_path.read_text(encoding="utf-8")) if split_path.exists() else None
    if isinstance(legacy, dict) and legacy.get("schema_version") == "2.0":
        legacy = legacy.get("legacy_indices")
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "dataset_sha256": dataset_hash,
                "seed": 42,
                "student_ids": stable_split,
                "indices": split_indices,
                "legacy_indices": legacy,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    student_texts = [row.get("feature_text") or row.get("thesis_title", "") for row in theses]
    advisor_texts = [row.get("profile_text") or row.get("skill_text") or row["advisor_name"] for row in advisors]
    builder = FeatureBuilder().fit(
        [student_texts[index] for index in split_indices["train"]],
        advisor_texts,
    )
    matrix, manifest = builder.compatibility(student_texts, advisor_texts)
    feature_root = root / "data/features"
    feature_root.mkdir(parents=True, exist_ok=True)
    np.save(feature_root / "compatibility_matrix_v2.npy", matrix, allow_pickle=False)
    manifest.update({"dataset_sha256": dataset_hash, "split_sha256": hashlib.sha256(split_path.read_bytes()).hexdigest()})
    (feature_root / "feature_manifest_v2.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"matrix_shape": list(matrix.shape), "matrix_sha256": manifest["matrix_sha256"]}))


if __name__ == "__main__":
    main()
