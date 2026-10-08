import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.baselines.greedy import greedy_assignment
from src.baselines.hungarian import hungarian_assignment
from src.baselines.random import random_assignment
from src.evaluation.metrics import load_variance, mean_compatibility, quota_violations


def main() -> None:
    root = Path(__file__).parents[1]
    scores = np.load(root / "data/features/compatibility_matrix_v2.npy", allow_pickle=False)
    capacities = np.full(scores.shape[1], int(np.ceil(scores.shape[0] / scores.shape[1])))
    methods = {
        "random_seed_42": random_assignment(scores.shape[0], capacities, seed=42),
        "greedy": greedy_assignment(scores, capacities),
        "hungarian_upper_bound": hungarian_assignment(scores, capacities),
    }
    metrics = {
        name: {
            "mean_compatibility": mean_compatibility(scores, assignments),
            "quota_violations": quota_violations(assignments, capacities),
            "load_variance": load_variance(assignments, scores.shape[1]),
        }
        for name, assignments in methods.items()
    }
    output = root / "outputs/baselines/v2026-09-28.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "scope": "validated-subset experiment",
                "capacity_policy": "uniform-ceiling",
                "students": scores.shape[0],
                "advisors": scores.shape[1],
                "metrics": metrics,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
