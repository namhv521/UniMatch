import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data_pipeline.crawl.provenance import SnapshotStore


QUEUE_FIELDS = [
    "queue_id", "advisor_id", "name_raw", "name_normalized", "attempted_urls",
    "last_attempt_at", "status", "failure_reason", "why_no_related_page",
    "suggested_search_queries", "user_provided_url", "assigned_at", "resolved_at",
]


def main() -> None:
    root = Path(__file__).parents[1]
    run_id = "baseline-advisor-crawl"
    cache = root / "data/cache/fit/lecturer.html"
    content = cache.read_bytes()
    store = SnapshotStore(root / "data/raw/crawl_snapshots", run_id=run_id)
    with (root / "data/curated/advisors.csv").open(encoding="utf-8-sig", newline="") as stream:
        unresolved = [row for row in csv.DictReader(stream) if row["needs_review"].lower() == "true"]
    now = datetime.now(UTC).isoformat()
    queue_rows = []
    for row in unresolved:
        url = row["source_url"]
        store.record(
            source_id="fit_lecturers",
            url=url,
            content=content,
            outcome="manual_required",
            http_status=200,
            content_type="text/html",
            error_code="identity_requires_review",
        )
        queue_rows.append(
            {
                "queue_id": f"advisor-{row['advisor_id']}",
                "advisor_id": row["advisor_id"],
                "name_raw": row["advisor_name"],
                "name_normalized": row["advisor_name"].casefold(),
                "attempted_urls": json.dumps([url], ensure_ascii=False),
                "last_attempt_at": now,
                "status": "manual_required",
                "failure_reason": "identity_requires_review",
                "why_no_related_page": "Profile evidence is incomplete or ambiguous.",
                "suggested_search_queries": json.dumps([row["advisor_name"]], ensure_ascii=False),
                "user_provided_url": "",
                "assigned_at": now,
                "resolved_at": "",
            }
        )
    queue = root / "data/manual_crawl_queue.csv"
    with queue.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=QUEUE_FIELDS)
        writer.writeheader()
        writer.writerows(queue_rows)
    print(json.dumps({"run_id": run_id, "manual_required": len(queue_rows)}))


if __name__ == "__main__":
    main()
