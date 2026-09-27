import json
from pathlib import Path

from src.data_pipeline.inventory import build_manifest


ROOT = Path(__file__).parents[2]


def test_baseline_manifest_records_required_roots_and_is_reproducible():
    manifest_path = ROOT / "outputs/data_quality/baseline_manifest.json"
    recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    rebuilt = build_manifest(ROOT)

    assert recorded == rebuilt
    assert set(recorded["roots"]) == {"curated", "extracted", "embeddings", "features"}
    assert all(item["status"] == "available" for item in recorded["roots"].values())
    assert all(item["file_count"] > 0 for item in recorded["roots"].values())
    assert all(len(item["sha256"]) == 64 for item in recorded["roots"].values())
    assert recorded["roots"]["curated"]["schemas"]["advisors.csv"][:2] == [
        "advisor_id",
        "advisor_name",
    ]
